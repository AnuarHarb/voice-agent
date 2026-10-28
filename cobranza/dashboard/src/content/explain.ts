import type { L10n } from './useCases'

export type Piece = { id: string; name: L10n; what: L10n; example: L10n; ai: boolean }

/** The six parts of a production voice agent, each with a real example from this project. */
export const anatomy: Piece[] = [
  {
    id: 'canal',
    name: { es: 'Canal de voz', en: 'Voice channel' },
    what: { es: 'Convierte la voz en texto, lo pasa al modelo y devuelve la respuesta hablada.', en: 'Turns speech into text, hands it to the model and speaks the answer back.' },
    example: { es: 'ElevenLabs Agents: reconocimiento de voz, modelo Claude Haiku y síntesis de voz en una sola plataforma.', en: 'ElevenLabs Agents: speech recognition, Claude Haiku and voice synthesis on one platform.' },
    ai: true,
  },
  {
    id: 'instrucciones',
    name: { es: 'Instrucciones', en: 'Instructions' },
    what: { es: 'Define quién es el agente, cómo habla y qué nunca hace.', en: 'Defines who the agent is, how it speaks and what it never does.' },
    example: { es: 'Un prompt de sistema compartido más un procedimiento por situación: verificación, acuerdo de pago, disputa, no contactar.', en: 'One shared system prompt plus one procedure per situation: verification, payment agreement, dispute, do not contact.' },
    ai: true,
  },
  {
    id: 'herramientas',
    name: { es: 'Herramientas', en: 'Tools' },
    what: { es: 'Funciones que el agente llama para consultar o ejecutar algo en los sistemas del cliente.', en: "Functions the agent calls to read from or act on the client's systems." },
    example: { es: 'Doce herramientas sobre una API: verify_identity, get_payment_options, create_payment_plan, send_payment_link y más.', en: 'Twelve tools over one API: verify_identity, get_payment_options, create_payment_plan, send_payment_link and more.' },
    ai: false,
  },
  {
    id: 'politica',
    name: { es: 'Política de negocio', en: 'Business policy' },
    what: { es: 'Las reglas que el negocio y la ley imponen, aplicadas por código.', en: 'The rules the business and the law impose, enforced by code.' },
    example: { es: 'Una política por producto: cuotas máximas, umbral de escalamiento a 60 días y horario de contacto de la Ley 2300.', en: 'One policy per product: maximum installments, a 60-day escalation threshold and Ley 2300 contact hours.' },
    ai: false,
  },
  {
    id: 'datos',
    name: { es: 'Datos y privacidad', en: 'Data and privacy' },
    what: { es: 'Cada cliente solo ve sus datos; la información personal vive aparte.', en: 'Each client sees only its own data; personal information is stored apart.' },
    example: { es: 'Postgres con seguridad por filas por cliente y una bóveda separada para datos personales. Tres intentos fallidos bloquean la sesión.', en: 'Postgres with per-client row-level security and a separate vault for personal data. Three failed attempts lock the session.' },
    ai: false,
  },
  {
    id: 'humano',
    name: { es: 'Humano en control', en: 'Human in control' },
    what: { es: 'Saber cuándo parar y pasar a una persona, con bitácora de todo lo hecho.', en: 'Knowing when to stop and hand off to a person, with a log of everything done.' },
    example: { es: 'Escalamiento, registro de disputa y opt-out inmediato. Cada llamada deja eventos, resultado y sentimiento en la consola.', en: 'Escalation, dispute registration and immediate opt-out. Every call leaves events, outcome and sentiment in the console.' },
    ai: false,
  },
]

export type Node = { name: L10n; detail: L10n; ai?: boolean }

export const integrationFlow: Node[] = [
  { name: { es: 'Canal', en: 'Channel' }, detail: { es: 'Teléfono, web o Telegram', en: 'Phone, web or Telegram' } },
  { name: { es: 'Agente', en: 'Agent' }, detail: { es: 'Voz, modelo e instrucciones', en: 'Voice, model and instructions' }, ai: true },
  { name: { es: 'API de herramientas', en: 'Tools API' }, detail: { es: 'Valida, aplica política, audita', en: 'Validates, applies policy, audits' } },
  { name: { es: 'Sistemas del cliente', en: 'Client systems' }, detail: { es: 'Core, CRM, pasarela de pagos', en: 'Core, CRM, payment gateway' } },
]

export const phases: { name: L10n; detail: L10n }[] = [
  { name: { es: 'Descubrimiento', en: 'Discovery' }, detail: { es: 'Elegimos una conversación y definimos qué es un buen resultado.', en: 'We pick one conversation and define what a good outcome is.' } },
  { name: { es: 'Prototipo', en: 'Prototype' }, detail: { es: 'Un agente funcionando con datos de prueba.', en: 'A working agent on test data.' } },
  { name: { es: 'Piloto', en: 'Pilot' }, detail: { es: 'Integración real con un grupo acotado de clientes y supervisión humana.', en: 'Real integration with a limited customer group and human oversight.' } },
  { name: { es: 'Producción', en: 'Production' }, detail: { es: 'Operación, métricas y mejora continua.', en: 'Operation, metrics and continuous improvement.' } },
]

/** Trimmed from tool_configs/get_account_summary.json. */
export const toolContract = `{
  "type": "webhook",
  "name": "get_account_summary",
  "description": "Returns the verified customer's masked account status.",
  "api_schema": {
    "url": "\${backend_url}/tools/account-summary",
    "method": "POST",
    "request_headers": { "X-Tenant-Key": { "secret_id": "..." } },
    "request_body_schema": {
      "required": ["session_token", "conversation_id"]
    }
  }
}`
