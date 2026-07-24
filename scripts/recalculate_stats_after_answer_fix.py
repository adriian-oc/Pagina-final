"""
Recalcula las notas/estadísticas de alumnos que se vieron afectadas por una corrección de
`correct_answer` en una pregunta (vía Admin o vía los scripts de corrección masiva de
Test de Teoría). El bug: la nota de un examen se calcula UNA VEZ, al terminarlo, usando el
snapshot de la pregunta guardado dentro de `exams.questions[]` en ese momento -- corregir
`questions.correct_answer` después no recalcula nada solo.

Compara por TEXTO de la opción correcta, no por índice numérico encadenado entre ediciones:
por cada examen que contiene la pregunta, busca dentro del propio snapshot (que puede tener
texto/opciones distintos si también se editaron, no solo el índice) cuál opción tiene el mismo
texto que la respuesta correcta ACTUAL de la pregunta -- así siempre converge al valor
correcto de verdad sin importar cuántas ediciones haya habido de por medio (una versión
anterior de este script encadenaba "valor viejo -> valor nuevo" de la edición más reciente y
podía dejar a medio corregir examenes anteriores a ediciones intermedias -- ver commit que
introduce este comentario).

Toca, para cada pregunta con `edit_history`:
  1. `exams.questions[].correct_answer` -- parchea el snapshot embebido.
  2. `attempts.score` / `attempts.details` -- para los intentos YA terminados con ese snapshot
     erróneo, recalcula la nota completa reutilizando `ExamService._calculate_score`.
  3. `user_theme_stats` / `analytics_failures` -- contadores ACUMULADOS por alumno, se
     reconstruyen desde cero reproduciendo TODOS los intentos terminados (ya corregidos) del
     alumno con `AnalyticsService.record_attempt_results`.
  4. `progress.content_scores[content_unit_key]` -- solo se actualizan `correct/total/pct` si
     el intento más reciente de esa unidad es uno de los corregidos (no se re-simula el estado
     SM-2 retroactivamente).

Uso:
  Comprobar sin escribir nada:
    cd backend && source venv/bin/activate && python ../scripts/recalculate_stats_after_answer_fix.py --dry-run

  Aplicar de verdad:
    cd backend && source venv/bin/activate && python ../scripts/recalculate_stats_after_answer_fix.py

Idempotente: si se relanza sin que haya correcciones nuevas de por medio, no encuentra nada que
tocar.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from config.database import connect_to_mongo, get_database  # noqa: E402
from services.exam_service import ExamService  # noqa: E402
from services.analytics_service import AnalyticsService  # noqa: E402


async def main(dry_run: bool):
    await connect_to_mongo()
    db = get_database()
    exam_service = ExamService()
    analytics_service = AnalyticsService()

    questions_with_history = await db.questions.find(
        {"edit_history": {"$exists": True, "$ne": []}}, {"_id": 0}
    ).to_list(length=None)
    print(f"Preguntas con historial de edición: {len(questions_with_history)}")

    # 1. Parchear snapshots de exámenes desactualizados (en memoria siempre; en Mongo solo si
    #    no es dry-run), comparando por texto de la opción correcta.
    patched_exams: dict[str, dict] = {}
    unresolved = 0
    for question in questions_with_history:
        if not question.get("choices") or question["correct_answer"] >= len(question["choices"]):
            continue
        current_correct_text = question["choices"][question["correct_answer"]]

        cursor = db.exams.find({"questions.question_id": question["id"]}, {"_id": 0})
        async for exam in cursor:
            changed = False
            for snap in exam["questions"]:
                if snap["question_id"] != question["id"]:
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
                    unresolved += 1
                    print(
                        f"  AVISO: examen {exam['id']} / pregunta {question['id']} -- el texto de la "
                        "respuesta correcta actual no aparece en el snapshot, se omite (revisar a mano)"
                    )
                    continue
                snap["correct_answer"] = right_index
                changed = True
            if changed:
                patched_exams[exam["id"]] = exam

    print(f"Exámenes con snapshot desactualizado: {len(patched_exams)}")
    print(f"Casos sin poder resolver por texto (requieren revisión manual): {unresolved}")
    if not dry_run:
        for exam_id, exam_doc in patched_exams.items():
            await db.exams.update_one({"id": exam_id}, {"$set": {"questions": exam_doc["questions"]}})

    # 2. Recalcular la nota de los intentos ya terminados sobre esos exámenes.
    exam_ids = list(patched_exams.keys())
    attempts_to_patch: dict[str, dict] = {}
    affected_users: set[str] = set()

    if exam_ids:
        cursor = db.attempts.find(
            {"exam_id": {"$in": exam_ids}, "finished_at": {"$ne": None}}, {"_id": 0}
        )
        async for attempt in cursor:
            exam_doc = patched_exams[attempt["exam_id"]]
            new_score = exam_service._calculate_score(
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

    print(f"Intentos terminados con nota a corregir: {len(attempts_to_patch)}")
    print(f"Alumnos afectados: {len(affected_users)}")

    if not dry_run:
        for attempt_id, patch in attempts_to_patch.items():
            await db.attempts.update_one(
                {"id": attempt_id},
                {"$set": {"score": patch["score"], "details": patch["details"]}},
            )

    # 3. Reconstruir user_theme_stats / analytics_failures desde cero para cada alumno afectado,
    #    reproduciendo TODOS sus intentos terminados (con la nota ya corregida donde aplique).
    progress_patches = 0
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
                print(f"  AVISO: intento {attempt['id']} de {user_id} sin 'details.results', se omite del recálculo")
                continue
            replay.append((attempt, correct, total, results))

        if not dry_run:
            await db.user_theme_stats.delete_many({"user_id": user_id})
            await db.analytics_failures.delete_many({"user_id": user_id})
            for attempt, _correct, _total, results in replay:
                await analytics_service.record_attempt_results(
                    attempt_id=attempt["id"], user_id=user_id, results=results
                )

        # 4. progress.content_scores: solo tocar si el intento MÁS RECIENTE de esa unidad
        #    (mode=practice) es uno de los que se acaban de corregir.
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
            if not existing:
                continue
            pct = round((correct / total) * 100, 2) if total else 0.0
            if existing.get("correct") == correct and existing.get("total") == total:
                continue
            progress_updates[f"content_scores.{key}.correct"] = correct
            progress_updates[f"content_scores.{key}.total"] = total
            progress_updates[f"content_scores.{key}.pct"] = pct
            progress_patches += 1

        if progress_updates and not dry_run:
            await db.progress.update_one({"user_id": user_id}, {"$set": progress_updates})

    print(f"Entradas de progress.content_scores a corregir (solo correct/total/pct): {progress_patches}")
    print()
    print("Modo simulación (--dry-run), no se ha escrito nada." if dry_run else "Cambios aplicados.")


if __name__ == "__main__":
    asyncio.run(main(dry_run="--dry-run" in sys.argv))
