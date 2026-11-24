# analysis/ — Самира · Business Analyst

Это пакет **бизнес-анализа**, передаваемый системному аналитику Милане. Сначала читать:

1. `01_business_context.md` — цели и границы.
2. `02_as_is_and_flows.md` — подтверждённые операции и гипотезы маршрутов.
3. `03_ideal_target_and_kpsc.md` — три состояния потока по МУ-17.
4. `04_to_be_hypotheses.md` — гипотезы улучшений и ожидаемые бизнес-эффекты.
5. `05_business_requirements.md` — потребности бизнеса, привязка к FR Миланы.
6. `06_glossary_and_kpi.md` — определение метрик, формулы и единицы.
7. `07_assumptions_and_gaps.md` — статус достоверности и ограничения.
8. `08_expert_questions.md` — вопросы для следующего контакта с экспертами.

Таблицы в `data/`: `operations_and_dependencies.csv`, `measurements_template.csv`, `loss_register.csv`, `source_reconciliation.csv`.

**Статус:** технически оформлены и пригодны для передачи; **НЕ согласованы с заказчиком**. Числа из стандартов — нормативы, не хронометраж.

Документ на первую защиту: `docs/СПЕЦИФИКАЦИЯ_ЭТАП_1.md`. Карты в обозначениях шаблона: `diagrams/kpsc_current.svg`, `kpsc_ideal.svg`, `kpsc_target.svg`. Таблицы в `data/` подписаны по-русски. База продукта: `../data/venio_stage1.sqlite`.
