# Playbook de manejo de excepciones de entrega

## Tipos de excepción y acción estándar

| Tipo | Causa típica | Acción estándar |
|------|--------------|-----------------|
| customs_hold | Documentación incompleta (CPF/CUIT faltante, valor sin declarar) | request_docs |
| invalid_address | Dirección incompleta o inexistente | notify_buyer |
| carrier_delay | Congestión del carrier de última milla | retry_delivery |
| lost_in_transit | Sin eventos por más de 30 días | mark_lost |

## customs_hold - Retención aduanera

Acción: **request_docs**. Solicitar al seller la factura comercial y al comprador el
documento de identidad fiscal (CPF en Brasil, CUIT/CUIL en Argentina, RFC en México)
dentro de las 24 horas de detectada la retención. Si la documentación no se obtiene
en 72 horas, escalar a equipo de aduanas (escalate). El plazo legal de depósito es
de 30 días en AR y BR, 45 en MX: agotado el plazo el paquete se devuelve a origen.

## invalid_address - Dirección inválida

Acción: **notify_buyer**. Contactar al comprador por email y SMS con link de
corrección de dirección. Máximo 2 intentos de contacto en 5 días. Si el comprador
corrige, reprogramar entrega (retry_delivery). Si no responde, devolver al hub local
y escalar al marketplace de origen (escalate).

## carrier_delay - Demora del carrier

Acción: **retry_delivery**. Reinyectar el paquete en la siguiente ventana de
distribución del carrier. Si el envío acumula más de 7 días sin movimiento en el
centro de distribución, reasignar a carrier alternativo del modelo multi-carrier
y registrar la penalidad de SLA del carrier original.

## lost_in_transit - Presunto extravío

Acción: **mark_lost**. Iniciar búsqueda formal con el carrier (plazo de respuesta
5 días hábiles). En paralelo, notificar al seller y abrir el expediente de
indemnización según la política de SLAs. Nunca prometer al comprador una fecha de
entrega durante una búsqueda activa.

## Criterio de escalamiento

Escalar a supervisor humano (escalate) siempre que: el valor declarado supere
USD 200, el comprador haya abierto un reclamo formal o disputa de pago, el envío
pertenezca a un marketplace con acuerdo de SLA premium, o la excepción no encaje
en ninguna categoría del playbook.
