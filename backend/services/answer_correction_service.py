import logging

from config.database import get_database

logger = logging.getLogger(__name__)


class AnswerCorrectionService:
    """Recalcula notas y estadísticas cuando cambia el correct_answer de una pregunta ya
    subida. La nota de un examen se calcula una sola vez, al terminarlo, contra un snapshot
    congelado de la pregunta guardado en `exams.questions[]` -- corregir `questions.correct_answer`
    después no recalcula nada solo. Ver `scripts/recalculate_stats_after_answer_fix.py` (versión
    en lote, para correcciones masivas ya aplicadas) -- esta clase es la misma lógica extraída
    para poder dispararse también en caliente, una sola pregunta a la vez, justo después de que
    un profesor/admin edite `correct_answer` desde Admin (ver `QuestionService.update_question`).

    Compara por TEXTO de la opción correcta (no por índice numérico ni por "valor viejo/nuevo"
    de una edición concreta): busca dentro del propio snapshot del examen qué opción tiene el
    mismo texto que la opción correcta ACTUAL de la pregunta, y ese es el índice correcto para
    ESE snapshot en particular. Esto es necesario porque una pregunta puede editarse varias
    veces seguidas (texto/opciones incluidos, no solo el índice) -- encadenar "de este valor a
    este otro" por cada edición deja a medio corregir cualquier examen anterior a la ÚLTIMA
    edición si no se re-evalúa contra el estado final; comparar por texto siempre converge al
    valor correcto de verdad, sin importar cuántas ediciones haya habido de por medio."""

    def __init__(self):
        self.db = get_database()
        # Import perezoso: evita el ciclo ExamService -> AnalyticsService/ProgressService ->
        # (nada que importe question_service), y mantiene este servicio ligero de instanciar
        # cuando no hace falta recalcular nada (la mayoría de ediciones no tocan correct_answer).
        from services.exam_service import ExamService
        from services.analytics_service import AnalyticsService
        self.exam_service = ExamService()
        self.analytics_service = AnalyticsService()

    async def recalculate_for_question(self, question_id: str) -> dict:
        """Recalcula todo lo afectado por el estado ACTUAL de `correct_answer` de una pregunta.
        Devuelve un resumen con lo tocado, para logging. Idempotente y seguro de re-ejecutar."""
        db = self.db

        question = await db.questions.find_one({"id": question_id}, {"_id": 0})
        if not question or not question.get("choices") or question["correct_answer"] >= len(question["choices"]):
            return {"exams_patched": 0, "attempts_patched": 0, "users_affected": 0, "progress_patched": 0}
        current_correct_text = question["choices"][question["correct_answer"]]

        # 1. Parchear el snapshot embebido en cualquier examen desactualizado: por cada uno,
        #    buscar dentro de SU PROPIO array de opciones (puede no coincidir con el actual si
        #    el texto también se editó) cuál tiene el mismo texto que la respuesta correcta de
        #    hoy. Si no aparece ningún texto igual, no se toca -- mejor dejarlo para revisión
        #    manual que adivinar un índice.
        patched_exams: dict[str, dict] = {}
        cursor = db.exams.find({"questions.question_id": question_id}, {"_id": 0})
        async for exam in cursor:
            changed = False
            for snap in exam["questions"]:
                if snap["question_id"] != question_id:
                    continue
                snap_choices = snap.get("choices") or []
                current_text = (
                    snap_choices[snap["correct_answer"]]
                    if 0 <= snap.get("correct_answer", -1) < len(snap_choices)
                    else None
                )
                if current_text == current_correct_text:
                    continue
                try:
                    right_index = snap_choices.index(current_correct_text)
                except ValueError:
                    logger.warning(
                        f"No se pudo recalcular examen {exam['id']} para pregunta {question_id}: "
                        "el texto de la respuesta correcta actual no aparece en el snapshot -- revisar a mano."
                    )
                    continue
                snap["correct_answer"] = right_index
                changed = True
            if changed:
                patched_exams[exam["id"]] = exam
                await db.exams.update_one({"id": exam["id"]}, {"$set": {"questions": exam["questions"]}})

        # 2. Recalcular la nota de los intentos ya terminados sobre esos exámenes.
        attempts_to_patch: dict[str, dict] = {}
        affected_users: set[str] = set()
        if patched_exams:
            cursor = db.attempts.find(
                {"exam_id": {"$in": list(patched_exams.keys())}, "finished_at": {"$ne": None}}, {"_id": 0}
            )
            async for attempt in cursor:
                exam_doc = patched_exams[attempt["exam_id"]]
                new_score = self.exam_service._calculate_score(
                    exam_doc["questions"], attempt.get("answers", {}), exam_doc["type"]
                )
                old_results = (attempt.get("details") or {}).get("results", [])
                if new_score["results"] != old_results:
                    attempts_to_patch[attempt["id"]] = {
                        "user_id": attempt["user_id"],
                        "score": new_score["final_score"],
                        "details": new_score,
                    }
                    affected_users.add(attempt["user_id"])
                    await db.attempts.update_one(
                        {"id": attempt["id"]},
                        {"$set": {"score": new_score["final_score"], "details": new_score}},
                    )

        # 3. Reconstruir user_theme_stats / analytics_failures desde cero para cada alumno
        #    afectado, reproduciendo TODOS sus intentos terminados (con la nota ya corregida).
        progress_patched = 0
        for user_id in affected_users:
            attempts = await db.attempts.find(
                {"user_id": user_id, "finished_at": {"$ne": None}}, {"_id": 0}
            ).sort("finished_at", 1).to_list(length=None)

            replay = []
            for attempt in attempts:
                if attempt["id"] in attempts_to_patch:
                    details = attempts_to_patch[attempt["id"]]["details"]
                    correct, total = details["correct"], details["total_questions"]
                else:
                    details = attempt.get("details") or {}
                    correct, total = details.get("correct", 0), details.get("total_questions", 0)
                results = details.get("results")
                if results is None:
                    continue
                replay.append((attempt, correct, total, results))

            await db.user_theme_stats.delete_many({"user_id": user_id})
            await db.analytics_failures.delete_many({"user_id": user_id})
            for attempt, _correct, _total, results in replay:
                await self.analytics_service.record_attempt_results(
                    attempt_id=attempt["id"], user_id=user_id, results=results
                )

            # 4. progress.content_scores: solo si el intento MÁS RECIENTE de esa unidad
            #    (mode=practice) es uno de los que se acaban de corregir. No se re-simula el
            #    estado SM-2 (ease_factor/repetitions/interval_days) retroactivamente.
            by_unit_latest: dict[str, tuple] = {}
            for attempt, correct, total, _results in replay:
                if attempt.get("mode") != "practice" or not attempt.get("content_unit_key"):
                    continue
                key = attempt["content_unit_key"]
                if key not in by_unit_latest or attempt["finished_at"] > by_unit_latest[key][0]["finished_at"]:
                    by_unit_latest[key] = (attempt, correct, total)

            progress_doc = await db.progress.find_one({"user_id": user_id}, {"_id": 0})
            content_scores = (progress_doc or {}).get("content_scores", {})
            progress_updates = {}
            for key, (attempt, correct, total) in by_unit_latest.items():
                if attempt["id"] not in attempts_to_patch:
                    continue
                existing = content_scores.get(key)
                if not existing or (existing.get("correct") == correct and existing.get("total") == total):
                    continue
                pct = round((correct / total) * 100, 2) if total else 0.0
                progress_updates[f"content_scores.{key}.correct"] = correct
                progress_updates[f"content_scores.{key}.total"] = total
                progress_updates[f"content_scores.{key}.pct"] = pct
                progress_patched += 1

            if progress_updates:
                await db.progress.update_one({"user_id": user_id}, {"$set": progress_updates})

        summary = {
            "exams_patched": len(patched_exams),
            "attempts_patched": len(attempts_to_patch),
            "users_affected": len(affected_users),
            "progress_patched": progress_patched,
        }
        logger.info(f"Recalculo para pregunta {question_id}: {summary}")
        return summary
