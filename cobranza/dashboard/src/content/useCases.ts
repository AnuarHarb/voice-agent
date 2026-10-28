export type Lang = 'es' | 'en'
export type L10n = Record<Lang, string>
export type L10nList = Record<Lang, string[]>

export type Industry = { id: string; name: L10n; summary: L10n }

export type ScriptLine =
  | { kind: 'agent' | 'user'; text: L10n }
  | { kind: 'tool'; name: string; result: L10n }

export type UseCase = {
  id: string
  industry: string
  title: L10n
  problem: L10n
  flow: L10nList
  tools: string[]
  guardrails: L10nList
  metric: L10n
  /** Label of the ElevenLabs agent in tenant_agents. Present only when a live demo exists. */
  demo?: { agentLabel: string; tenant: string; productCode: string; agentName: string }
  script: ScriptLine[]
}

export const industries: Industry[] = [
  {
    id: 'finanzas',
    name: { es: 'Servicios financieros', en: 'Financial services' },
    summary: {
      es: 'Cobranza, recordatorios y ofertas de crédito. Cinco agentes en operación de demo.',
      en: 'Collections, reminders and credit offers. Five agents running as live demos.',
    },
  },
  {
    id: 'salud',
    name: { es: 'Salud', en: 'Healthcare' },
    summary: {
      es: 'Agenda de citas y confirmaciones sin saturar la línea de la clínica.',
      en: 'Appointment booking and confirmations without overloading the clinic line.',
    },
  },
  {
    id: 'retail',
    name: { es: 'Retail y e-commerce', en: 'Retail and e-commerce' },
    summary: {
      es: 'Pedidos, devoluciones y carritos abandonados por voz.',
      en: 'Orders, returns and abandoned carts by voice.',
    },
  },
  {
    id: 'telco',
    name: { es: 'Telecomunicaciones y servicios', en: 'Telecom and utilities' },
    summary: {
      es: 'Soporte de primer nivel y retención antes de la cancelación.',
      en: 'First-level support and retention before cancellation.',
    },
  },
  {
    id: 'inmobiliaria',
    name: { es: 'Inmobiliaria y ventas B2B', en: 'Real estate and B2B sales' },
    summary: {
      es: 'Calificación de leads entrantes y cita con un asesor.',
      en: 'Inbound lead qualification and a booked call with an advisor.',
    },
  },
]

export const useCases: UseCase[] = [
  {
    id: 'tarjeta-preventiva',
    industry: 'finanzas',
    title: { es: 'Tarjeta de crédito: aviso preventivo', en: 'Credit card: preventive reminder' },
    problem: {
      es: 'El cliente olvida la fecha de pago y entra en mora sin querer. Avisar antes cuesta menos que cobrar después.',
      en: 'Customers forget the due date and fall behind by accident. Reminding them costs less than collecting later.',
    },
    flow: {
      es: [
        'Verifica identidad con dos datos antes de decir cualquier cifra.',
        'Lee pago mínimo, pago total y fecha límite.',
        'Si el saldo lo permite, ofrece rediferir a 6, 12 o 24 cuotas, como oferta aparte.',
        'Envía el link de pago por Telegram.',
      ],
      en: [
        'Verifies identity with two data points before saying any figure.',
        'Reads the minimum payment, total balance and due date.',
        'If the balance allows it, offers to refinance over 6, 12 or 24 installments, as a separate offer.',
        'Sends the payment link over Telegram.',
      ],
    },
    tools: ['verify_identity', 'get_account_summary', 'get_payment_options', 'create_payment_plan', 'send_payment_link'],
    guardrails: {
      es: ['Solo ofrece opciones que la política del producto permite.', 'Respeta la ventana de contacto de la Ley 2300.', 'Tres intentos fallidos de identidad bloquean la sesión.'],
      en: ['Only offers options the product policy allows.', 'Respects the Ley 2300 contact window.', 'Three failed identity attempts lock the session.'],
    },
    metric: { es: 'Pagos antes del vencimiento', en: 'Payments before the due date' },
    demo: { agentLabel: 'tarjeta_preventiva', tenant: 'avanza', productCode: 'tarjeta', agentName: 'Valentina' },
    script: [
      { kind: 'agent', text: { es: 'Hola, soy Valentina, asistente de inteligencia artificial de Banco Avanza. Te llamo por tu tarjeta. ¿Hablo con Diana?', en: "Hi, I'm Valentina, Banco Avanza's AI assistant. I'm calling about your card. Am I speaking with Diana?" } },
      { kind: 'user', text: { es: 'Sí, soy yo.', en: "Yes, it's me." } },
      { kind: 'tool', name: 'verify_identity', result: { es: 'Identidad verificada', en: 'Identity verified' } },
      { kind: 'tool', name: 'get_account_summary', result: { es: 'Mínimo $380.000, vence en 3 días', en: 'Minimum $380,000, due in 3 days' } },
      { kind: 'agent', text: { es: 'Tu pago mínimo es de trescientos ochenta mil pesos y vence en tres días. ¿Quieres que te envíe el link de pago?', en: 'Your minimum payment is three hundred eighty thousand pesos, due in three days. Want me to send the payment link?' } },
    ],
  },
  {
    id: 'libre-inversion-mora',
    industry: 'finanzas',
    title: { es: 'Libre inversión: mora temprana', en: 'Personal loan: early arrears' },
    problem: {
      es: 'Una cuota vencida hace pocos días se resuelve con una conversación corta, si el cliente tiene un acuerdo realista a la mano.',
      en: 'A payment a few days overdue is solved in a short conversation, if the customer has a realistic agreement within reach.',
    },
    flow: {
      es: [
        'Verifica identidad y confirma que habla con el titular.',
        'Informa el valor vencido, sin preguntar el motivo del impago.',
        'Ofrece pago total, hasta 3 cuotas o un plan por dificultad económica.',
        'Registra el acuerdo y envía el link de pago.',
      ],
      en: [
        'Verifies identity and confirms the speaker is the account holder.',
        'States the overdue amount, without asking why the payment was missed.',
        'Offers full payment, up to 3 installments, or a hardship plan.',
        'Registers the agreement and sends the payment link.',
      ],
    },
    tools: ['verify_identity', 'get_payment_options', 'create_payment_plan', 'send_payment_link', 'register_dispute', 'register_opt_out'],
    guardrails: {
      es: ['El código decide los montos; el modelo solo los comunica.', 'Si el cliente disputa la deuda, la cobranza se pausa.', 'Si pide que no lo llamen, queda registrado al instante.'],
      en: ['Code decides the amounts; the model only communicates them.', 'If the customer disputes the debt, collection pauses.', 'If they ask not to be called, it is recorded immediately.'],
    },
    metric: { es: 'Acuerdos de pago registrados', en: 'Payment agreements registered' },
    demo: { agentLabel: 'libre_inversion_mora', tenant: 'avanza', productCode: 'libre_inversion', agentName: 'Sofía' },
    script: [
      { kind: 'agent', text: { es: 'Tienes una cuota vencida de novecientos cincuenta mil pesos. Puedes pagarla completa o en hasta tres cuotas.', en: 'You have an overdue payment of nine hundred fifty thousand pesos. You can pay it in full or in up to three installments.' } },
      { kind: 'user', text: { es: 'En dos cuotas, por favor.', en: 'Two installments, please.' } },
      { kind: 'tool', name: 'create_payment_plan', result: { es: 'Plan de 2 cuotas registrado', en: '2-installment plan registered' } },
      { kind: 'tool', name: 'send_payment_link', result: { es: 'Link enviado por Telegram', en: 'Link sent over Telegram' } },
    ],
  },
  {
    id: 'vehiculo-mora',
    industry: 'finanzas',
    title: { es: 'Vehículo: mora media y escalamiento', en: 'Auto loan: mid-stage arrears and escalation' },
    problem: {
      es: 'Con más de 60 días de mora, el margen de negociación del agente termina. Debe saber cuándo pasar el caso a una persona.',
      en: 'Past 60 days overdue, the agent has no negotiation room left. It must know when to hand the case to a person.',
    },
    flow: {
      es: [
        'Verifica identidad.',
        'Presenta hasta 2 cuotas, sin plan de dificultad.',
        'Si la mora supera 60 días, no negocia: escala a un asesor humano.',
        'Deja la bitácora completa del caso.',
      ],
      en: [
        'Verifies identity.',
        'Presents up to 2 installments, no hardship plan.',
        'If arrears exceed 60 days, it does not negotiate: it escalates to a human advisor.',
        'Leaves a complete case log.',
      ],
    },
    tools: ['verify_identity', 'get_payment_options', 'create_payment_plan', 'request_callback'],
    guardrails: {
      es: ['El umbral de escalamiento vive en la política, no en el prompt.', 'El agente se identifica como IA desde la primera frase.'],
      en: ['The escalation threshold lives in policy, not in the prompt.', 'The agent identifies itself as AI in the first sentence.'],
    },
    metric: { es: 'Casos escalados a tiempo', en: 'Cases escalated on time' },
    demo: { agentLabel: 'vehiculo_mora', tenant: 'avanza', productCode: 'vehiculo', agentName: 'Ricardo' },
    script: [
      { kind: 'tool', name: 'get_payment_options', result: { es: 'Mora de 75 días: escalar', en: '75 days overdue: escalate' } },
      { kind: 'agent', text: { es: 'Por el tiempo de mora, este caso lo atiende un asesor. Te va a llamar en el horario permitido.', en: 'Because of how long the account has been overdue, an advisor will handle it. They will call you within allowed hours.' } },
      { kind: 'tool', name: 'request_callback', result: { es: 'Llamada de asesor programada', en: 'Advisor callback scheduled' } },
    ],
  },
  {
    id: 'microcredito',
    industry: 'finanzas',
    title: { es: 'Microcrédito: promesa de pago', en: 'Microloan: promise to pay' },
    problem: {
      es: 'Los montos son pequeños y el cliente suele pagar en efectivo. Lo que sirve es una promesa con fecha, no un plan complejo.',
      en: 'Amounts are small and customers often pay in cash. What works is a dated promise, not a complex plan.',
    },
    flow: {
      es: ['Verifica identidad.', 'Informa el saldo vencido.', 'Pide una fecha de pago de máximo 7 días.', 'Envía el link y deja la promesa registrada.'],
      en: ['Verifies identity.', 'States the overdue balance.', 'Asks for a payment date within 7 days.', 'Sends the link and records the promise.'],
    },
    tools: ['verify_identity', 'get_payment_options', 'create_payment_plan', 'send_payment_link'],
    guardrails: {
      es: ['La fecha prometida no puede pasar de 7 días.', 'Llamadas cortas: una sola oferta.'],
      en: ['The promised date cannot exceed 7 days.', 'Short calls: one offer only.'],
    },
    metric: { es: 'Promesas cumplidas', en: 'Promises kept' },
    demo: { agentLabel: 'microcredito', tenant: 'avanza', productCode: 'microcredito', agentName: 'Lucía' },
    script: [
      { kind: 'agent', text: { es: 'Tienes ciento ochenta y cinco mil pesos vencidos. ¿Para qué día en esta semana te queda bien pagar?', en: 'You have one hundred eighty-five thousand pesos overdue. What day this week works for you to pay?' } },
      { kind: 'user', text: { es: 'El viernes.', en: 'Friday.' } },
      { kind: 'tool', name: 'create_payment_plan', result: { es: 'Promesa registrada para el viernes', en: 'Promise registered for Friday' } },
    ],
  },
  {
    id: 'oferta-cupo',
    industry: 'finanzas',
    title: { es: 'Oferta comercial de cupo con OTP', en: 'Credit line offer with OTP' },
    problem: {
      es: 'Clientes al día con cupo disponible. La oferta solo puede hacerse con consentimiento comercial y el desembolso exige confirmación.',
      en: 'Customers in good standing with available credit. The offer requires commercial consent and disbursement requires confirmation.',
    },
    flow: {
      es: [
        'Verifica identidad y consentimiento comercial.',
        'Presenta monto, tasa y plazos disponibles.',
        'Simula la cuota con el plazo elegido y lee el costo total.',
        'Envía un código OTP por Telegram; solo el código correcto desembolsa.',
      ],
      en: [
        'Verifies identity and commercial consent.',
        'Presents amount, rate and available terms.',
        'Simulates the installment for the chosen term and reads the total cost.',
        'Sends an OTP over Telegram; only the correct code disburses.',
      ],
    },
    tools: ['verify_identity', 'get_credit_offer', 'simulate_offer', 'request_disbursement_otp', 'confirm_disbursement', 'register_opt_out'],
    guardrails: {
      es: ['Un "no" cierra la oferta y no se vuelve a insistir.', 'Nunca dice "preaprobado" antes de confirmar el desembolso.', 'El OTP vence y tiene intentos limitados.'],
      en: ['A "no" closes the offer and the agent does not push again.', 'Never says "pre-approved" before disbursement is confirmed.', 'The OTP expires and has limited attempts.'],
    },
    metric: { es: 'Conversión de oferta a desembolso', en: 'Offer-to-disbursement conversion' },
    demo: { agentLabel: 'oferta_cupo', tenant: 'avanza', productCode: 'libre_inversion', agentName: 'Mateo' },
    script: [
      { kind: 'tool', name: 'get_credit_offer', result: { es: '$5.000.000 a 24,5 % E.A.', en: '$5,000,000 at 24.5% APR' } },
      { kind: 'tool', name: 'simulate_offer', result: { es: '24 cuotas, costo total calculado', en: '24 installments, total cost calculated' } },
      { kind: 'tool', name: 'request_disbursement_otp', result: { es: 'Código enviado por Telegram', en: 'Code sent over Telegram' } },
      { kind: 'tool', name: 'confirm_disbursement', result: { es: 'Desembolso confirmado', en: 'Disbursement confirmed' } },
    ],
  },
  {
    id: 'salud-citas',
    industry: 'salud',
    title: { es: 'Agenda y confirmación de citas', en: 'Appointment booking and confirmation' },
    problem: {
      es: 'Las llamadas de agenda saturan la línea y las citas no confirmadas se pierden.',
      en: 'Scheduling calls overload the line and unconfirmed appointments are lost.',
    },
    flow: {
      es: ['Confirma identidad del paciente.', 'Consulta disponibilidad del especialista.', 'Agenda, reprograma o cancela.', 'Envía el recordatorio por mensaje.'],
      en: ['Confirms patient identity.', "Checks the specialist's availability.", 'Books, reschedules or cancels.', 'Sends a message reminder.'],
    },
    tools: ['verify_patient', 'get_availability', 'book_appointment', 'cancel_appointment', 'send_reminder'],
    guardrails: {
      es: ['No da información clínica por voz.', 'Síntomas urgentes pasan a una persona de inmediato.'],
      en: ['Gives no clinical information by voice.', 'Urgent symptoms go to a person immediately.'],
    },
    metric: { es: 'Inasistencias evitadas', en: 'No-shows avoided' },
    script: [
      { kind: 'user', text: { es: 'Necesito mover mi cita del jueves.', en: 'I need to move my Thursday appointment.' } },
      { kind: 'tool', name: 'get_availability', result: { es: 'Dos espacios el viernes', en: 'Two slots on Friday' } },
      { kind: 'agent', text: { es: 'Tengo viernes a las 9 y a las 11. ¿Cuál prefieres?', en: 'I have Friday at 9 and 11. Which do you prefer?' } },
    ],
  },
  {
    id: 'retail-pedidos',
    industry: 'retail',
    title: { es: 'Estado de pedidos y devoluciones', en: 'Order status and returns' },
    problem: {
      es: '"¿Dónde está mi pedido?" es la consulta más repetida. Un agente la resuelve sin cola.',
      en: '"Where is my order?" is the most repeated query. An agent answers it with no queue.',
    },
    flow: {
      es: ['Identifica al cliente por número de pedido y un dato de verificación.', 'Informa el estado del envío.', 'Abre la devolución si cumple la política.', 'Envía la guía por mensaje.'],
      en: ['Identifies the customer by order number and a verification detail.', 'Reports shipping status.', 'Opens the return if it meets policy.', 'Sends the label by message.'],
    },
    tools: ['lookup_order', 'get_tracking', 'open_return', 'send_label'],
    guardrails: {
      es: ['La política de devolución la aplica el código.', 'Reembolsos fuera de política pasan a una persona.'],
      en: ['Code applies the return policy.', 'Out-of-policy refunds go to a person.'],
    },
    metric: { es: 'Consultas resueltas sin agente humano', en: 'Queries resolved without a human agent' },
    script: [
      { kind: 'tool', name: 'get_tracking', result: { es: 'En reparto, llega hoy', en: 'Out for delivery, arrives today' } },
      { kind: 'agent', text: { es: 'Tu pedido salió a reparto esta mañana y llega hoy antes de las 6.', en: 'Your order went out for delivery this morning and arrives today before 6.' } },
    ],
  },
  {
    id: 'retail-carritos',
    industry: 'retail',
    title: { es: 'Recuperación de carritos abandonados', en: 'Abandoned cart recovery' },
    problem: {
      es: 'Un carrito lleno sin pago es una venta a medias. Una llamada corta con consentimiento puede cerrarla.',
      en: 'A full cart with no payment is a half-made sale. A short consented call can close it.',
    },
    flow: {
      es: ['Verifica consentimiento comercial.', 'Pregunta si hubo un problema con el pago.', 'Resuelve la duda o envía el link de pago.', 'Un "no" cierra el contacto.'],
      en: ['Checks commercial consent.', 'Asks if something went wrong at checkout.', 'Answers the question or sends the payment link.', 'A "no" ends the contact.'],
    },
    tools: ['get_cart', 'send_checkout_link', 'register_opt_out'],
    guardrails: {
      es: ['Solo llama a quien dio consentimiento.', 'Una sola oferta por llamada.'],
      en: ['Only calls people who gave consent.', 'One offer per call.'],
    },
    metric: { es: 'Carritos recuperados', en: 'Carts recovered' },
    script: [
      { kind: 'agent', text: { es: 'Dejaste unos zapatos en tu carrito. ¿Tuviste algún problema para pagar?', en: 'You left a pair of shoes in your cart. Did you have trouble at checkout?' } },
    ],
  },
  {
    id: 'telco-soporte',
    industry: 'telco',
    title: { es: 'Soporte de primer nivel', en: 'First-level support' },
    problem: {
      es: 'Reinicios, facturas y fallas conocidas ocupan a los asesores en lo que un agente puede resolver.',
      en: 'Resets, invoices and known outages occupy advisors with what an agent can resolve.',
    },
    flow: {
      es: ['Identifica la línea o el servicio.', 'Revisa fallas masivas conocidas.', 'Guía el diagnóstico paso a paso.', 'Si no se resuelve, crea el ticket y transfiere con contexto.'],
      en: ['Identifies the line or service.', 'Checks known outages.', 'Walks through diagnosis step by step.', 'If unresolved, opens a ticket and transfers with context.'],
    },
    tools: ['lookup_service', 'check_outage', 'run_diagnostic', 'create_ticket'],
    guardrails: {
      es: ['Cambios de plan o cobros pasan a una persona.', 'La transferencia incluye el resumen para no repetir la historia.'],
      en: ['Plan changes or charges go to a person.', 'The transfer includes a summary so the customer does not repeat the story.'],
    },
    metric: { es: 'Resolución en primer contacto', en: 'First-contact resolution' },
    script: [
      { kind: 'tool', name: 'check_outage', result: { es: 'Sin falla en la zona', en: 'No outage in the area' } },
      { kind: 'tool', name: 'run_diagnostic', result: { es: 'Módem sin respuesta, reinicio remoto', en: 'Modem unresponsive, remote restart' } },
    ],
  },
  {
    id: 'telco-retencion',
    industry: 'telco',
    title: { es: 'Retención antes de la cancelación', en: 'Retention before cancellation' },
    problem: {
      es: 'Quien pide cancelar suele tener un motivo concreto: precio, falla o cambio de necesidad.',
      en: 'People asking to cancel usually have a concrete reason: price, a fault, or a changed need.',
    },
    flow: {
      es: ['Escucha el motivo.', 'Consulta las ofertas de retención vigentes.', 'Presenta una opción, no una lista.', 'Si el cliente insiste, procesa la cancelación sin trabas.'],
      en: ['Listens to the reason.', 'Looks up current retention offers.', 'Presents one option, not a list.', 'If the customer insists, processes the cancellation with no friction.'],
    },
    tools: ['lookup_service', 'get_retention_offer', 'apply_offer', 'process_cancellation'],
    guardrails: {
      es: ['Nunca bloquea una cancelación solicitada.', 'Las ofertas salen de un catálogo, no se inventan.'],
      en: ['Never blocks a requested cancellation.', 'Offers come from a catalog, never invented.'],
    },
    metric: { es: 'Clientes retenidos', en: 'Customers retained' },
    script: [
      { kind: 'user', text: { es: 'Quiero cancelar, está muy caro.', en: 'I want to cancel, it is too expensive.' } },
      { kind: 'tool', name: 'get_retention_offer', result: { es: '20 % por 6 meses', en: '20% off for 6 months' } },
    ],
  },
  {
    id: 'inmobiliaria-leads',
    industry: 'inmobiliaria',
    title: { es: 'Calificación de leads y cita con asesor', en: 'Lead qualification and advisor booking' },
    problem: {
      es: 'Los leads llegan a cualquier hora y enfriarse cuesta ventas. El agente califica al instante y agenda.',
      en: 'Leads arrive at any hour and going cold costs sales. The agent qualifies instantly and books.',
    },
    flow: {
      es: ['Llama al lead entrante en minutos.', 'Califica presupuesto, zona y plazo.', 'Agenda una visita o llamada con un asesor.', 'Entrega el resumen al CRM.'],
      en: ['Calls the inbound lead within minutes.', 'Qualifies budget, area and timeline.', 'Books a visit or call with an advisor.', 'Writes the summary to the CRM.'],
    },
    tools: ['get_lead', 'score_lead', 'book_advisor', 'update_crm'],
    guardrails: {
      es: ['No promete precios ni disponibilidad que no estén en el inventario.', 'El asesor humano cierra la venta.'],
      en: ['Never promises prices or availability that are not in inventory.', 'The human advisor closes the sale.'],
    },
    metric: { es: 'Leads calificados con cita', en: 'Qualified leads with a booked meeting' },
    script: [
      { kind: 'agent', text: { es: 'Vi tu interés en apartamentos en Chapinero. ¿Qué presupuesto manejas?', en: 'I saw your interest in apartments in Chapinero. What budget are you working with?' } },
    ],
  },
]

export const useCaseById = (id: string) => useCases.find((c) => c.id === id)
export const casesOf = (industry: string) => useCases.filter((c) => c.industry === industry)
export const industryById = (id: string) => industries.find((i) => i.id === id)
