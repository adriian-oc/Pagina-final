import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { contestService } from '../services/contestService';
import ContestCountdown from '../components/ContestCountdown';

const FEATURES = [
  {
    icon: '📘',
    title: 'Temario actualizado',
    text: 'Parte General y Específica al día con los últimos cambios normativos, organizado por tema.',
  },
  {
    icon: '📝',
    title: 'Supuestos prácticos y cuadernillos',
    text: 'Practica con casos reales tipo examen, con corrección detallada pregunta a pregunta.',
  },
  {
    icon: '👥',
    title: 'Profesor asignado',
    text: 'Cada alumno tiene un profesor de referencia y un chat directo para resolver dudas.',
  },
  {
    icon: '📄',
    title: 'Materiales exclusivos',
    text: 'Esquemas, Test de Teoría y documentos que tu profesor sube y aprueba para tu grupo.',
  },
  {
    icon: '📊',
    title: 'Seguimiento real de tu progreso',
    text: 'Una sola pantalla con tus notas, tu evolución por tema y tu historial completo de exámenes.',
  },
  {
    icon: '🔁',
    title: 'Calendario de repaso inteligente',
    text: 'Te decimos qué repasar y cuándo, antes de que se te olvide -- no solo qué es nuevo.',
  },
];

const STEPS = [
  { n: '1', title: 'Solicita acceso', text: 'Cuéntanos en qué punto estás de tu preparación.' },
  { n: '2', title: 'Te asignamos profesor y contenido', text: 'Acceso a tu temario, cuadernillos y calendario.' },
  { n: '3', title: 'Practicas con seguimiento real', text: 'Cada práctica ajusta qué repasar y cuándo.' },
];

const Landing = () => {
  const [contestConfig, setContestConfig] = useState(null);

  useEffect(() => {
    contestService.getConfig().then(setContestConfig).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-white text-gray-900">
      {/* Barra superior: marca + acceso, sin más navegación que distraiga */}
      <header className="border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center">
            <img src="/branding/logo.png" alt="ADOC" className="h-12 w-auto object-contain" />
          </Link>
          <Link
            to="/login"
            className="px-4 py-2 text-sm font-medium text-primary-700 border border-primary-200 rounded-md hover:bg-primary-50"
            data-testid="landing-login-link"
          >
            Iniciar sesión
          </Link>
        </div>
      </header>

      {/* Concurso de Acceso -- campaña con fecha límite, destacada al principio de todo */}
      {contestConfig && (
        <section className="bg-gray-900 text-white">
          <div className="max-w-4xl mx-auto px-6 py-10 text-center">
            <p className="text-sm font-semibold text-amber-400 uppercase tracking-wide mb-2">
              Concurso de acceso ADOC Oposiciones
            </p>
            <h2 className="text-2xl sm:text-3xl font-bold">¿Crees que puedes estar entre los mejores?</h2>
            <p className="mt-2 text-gray-300">
              Solo 300 personas podrán participar. Tu nota determinará tu premio: desde acceso
              gratis 1 año hasta 30 €/mes.
            </p>
            <div className="mt-6 flex justify-center">
              <ContestCountdown endAt={contestConfig.end_at} />
            </div>
            <Link
              to="/concurso"
              className="mt-6 inline-block px-6 py-3 bg-amber-400 text-amber-950 rounded-md font-semibold hover:bg-amber-300"
            >
              Inscríbete aquí
            </Link>
          </div>
        </section>
      )}

      {/* Hero -- responde en los primeros 5 segundos qué es, para quién y por qué importa */}
      <section className="bg-gradient-to-br from-primary-50 to-white">
        <div className="max-w-4xl mx-auto px-6 py-20 text-center">
          <p className="text-sm font-semibold text-primary-600 uppercase tracking-wide mb-3">
            Academia de Oposiciones C1
          </p>
          <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-900 leading-tight">
            Preparándote hoy, consigues tu plaza mañana
          </h1>
          <p className="mt-5 text-lg text-gray-600 max-w-2xl mx-auto">
            Temario actualizado, supuestos prácticos y un profesor que sigue tu evolución de
            verdad -- con un calendario de repaso que te dice qué tocar cada día para que no se
            te olvide lo que ya sabías.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/solicitar-acceso"
              className="px-6 py-3 bg-primary-600 text-white rounded-md font-semibold hover:bg-primary-700"
              data-testid="landing-cta-student"
            >
              Quiero preparar mi oposición
            </Link>
          </div>
        </div>
      </section>

      {/* Qué incluye */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <h2 className="text-2xl sm:text-3xl font-bold text-center text-gray-900">Todo lo que necesitas en un solo sitio</h2>
        <p className="mt-2 text-center text-gray-500 max-w-xl mx-auto">
          Nada de apuntes sueltos ni exámenes descoordinados: un único espacio pensado para
          opositar.
        </p>
        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map((f) => (
            <div key={f.title} className="border border-gray-100 rounded-lg p-6 hover:shadow-md transition-shadow">
              <div className="text-3xl mb-3">{f.icon}</div>
              <h3 className="font-semibold text-gray-900 mb-1">{f.title}</h3>
              <p className="text-sm text-gray-600">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Diferenciador real: repetición espaciada, con la ciencia detrás */}
      <section className="bg-gray-50 border-y border-gray-100">
        <div className="max-w-4xl mx-auto px-6 py-16 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-gray-900">Repasa justo cuando toca, no cuando ya se te ha olvidado</h2>
          <p className="mt-4 text-gray-600">
            La memoria se olvida en curva, no de golpe: repasar un tema demasiado tarde obliga a
            reaprenderlo casi entero, y repasarlo demasiado pronto es tiempo perdido. Nuestro
            calendario de estudio aplica el mismo principio de repetición espaciada que llevan
            décadas usando los sistemas de estudio más efectivos (el algoritmo SM-2 y la curva
            del olvido de Ebbinghaus): cada tema que practicas vuelve a aparecer justo antes de
            que empieces a olvidarlo, y los que dominas dejan de quitarte tiempo.
          </p>
        </div>
      </section>

      {/* Cómo funciona -- reduce fricción explicando el proceso */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <h2 className="text-2xl sm:text-3xl font-bold text-center text-gray-900">Cómo empezar</h2>
        <div className="mt-10 grid grid-cols-1 sm:grid-cols-3 gap-8">
          {STEPS.map((s) => (
            <div key={s.n} className="text-center">
              <div className="mx-auto w-10 h-10 rounded-full bg-primary-600 text-white flex items-center justify-center font-bold mb-3">
                {s.n}
              </div>
              <h3 className="font-semibold text-gray-900">{s.title}</h3>
              <p className="text-sm text-gray-600 mt-1">{s.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA final -- refuerza la acción con las dos vías de entrada */}
      <section className="bg-primary-600">
        <div className="max-w-3xl mx-auto px-6 py-14 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white">¿Empezamos?</h2>
          <p className="mt-2 text-primary-100">
            Cuéntanos tu situación y te contactamos para empezar cuanto antes.
          </p>
          <div className="mt-6 flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/solicitar-acceso"
              className="px-6 py-3 bg-white text-primary-700 rounded-md font-semibold hover:bg-primary-50"
            >
              Quiero preparar mi oposición
            </Link>
          </div>
          <Link to="/login" className="mt-5 inline-block text-sm text-primary-100 hover:text-white">
            ¿Ya tienes cuenta? Inicia sesión
          </Link>
        </div>
      </section>

      <footer className="max-w-6xl mx-auto px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-3 text-sm text-gray-500">
        <div className="flex items-center gap-2">
          <img src="/branding/logo.png" alt="ADOC" className="h-8 w-auto object-contain" />
          <span>Academia de Oposiciones C1</span>
        </div>
        <div className="flex items-center gap-4">
          <a href="mailto:Oposicionesadoc@gmail.com" className="hover:text-primary-600">Oposicionesadoc@gmail.com</a>
          <a href="https://instagram.com/oposicionesadoc" target="_blank" rel="noopener noreferrer" className="hover:text-primary-600">
            @oposicionesadoc
          </a>
          <Link to="/trabaja-con-nosotros" className="hover:text-primary-600" data-testid="landing-cta-teacher">
            ¿Eres profesor?
          </Link>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
