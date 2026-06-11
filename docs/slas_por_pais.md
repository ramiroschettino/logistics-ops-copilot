# SLAs de entrega por país y nivel de servicio

## Tiempos de tránsito comprometidos (puerta a puerta, días hábiles)

| Destino | Standard | Registered | Express |
|---------|----------|------------|---------|
| Argentina (AR) | 15-25 | 12-18 | 7-10 |
| Brasil (BR) | 12-20 | 10-15 | 5-8 |
| México (MX) | 10-18 | 8-14 | 4-7 |
| Chile (CL) | 12-20 | 10-16 | 6-9 |
| Colombia (CO) | 12-22 | 10-16 | 6-9 |
| Perú (PE) | 14-24 | 12-18 | 7-10 |

Los tiempos se miden desde el evento EMB (salida de oficina de cambio de origen) hasta
EMI (entregado). El tránsito aduanero está incluido salvo retenciones por documentación
atribuibles al seller o al comprador.

## Umbrales de alerta operativa

Un envío se considera "en riesgo de SLA" cuando supera el 80% del tiempo comprometido
sin evento de entrega. Se considera "stuck" (atascado) cuando no registra ningún evento
nuevo en 4 o más días corridos. Un envío sin eventos por más de 30 días desde EMB se
presume extraviado y dispara el proceso de indemnización.

## Política de indemnización

Envíos registered y express extraviados se indemnizan al 100% del valor declarado con
tope de USD 200. Envíos standard se indemnizan con tope de USD 40. El reclamo debe
iniciarse dentro de los 60 días del último evento de tracking. Requiere: número de
tracking, factura de compra y declaración jurada del comprador.

## Métricas de calidad por carrier

El desempeño de cada carrier de última milla se mide mensualmente: porcentaje de
entregas dentro de SLA (objetivo ≥ 92%), tasa de primer intento exitoso (objetivo
≥ 85%) y tasa de excepciones (objetivo ≤ 3%). Carriers bajo objetivo dos meses
consecutivos pasan a plan de remediación y se redistribuye su volumen.
