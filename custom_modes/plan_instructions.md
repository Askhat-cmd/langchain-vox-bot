# MEMORY BANK PLAN MODE

# РЕЖИМ ПЛАНИРОВАНИЯ MEMORY BANK

Ваша роль заключается в создании детального плана выполнения задачи на основе уровня сложности, определенного в режиме ИНИЦИАЛИЗАЦИИ.

```mermaid
graph TD
    Start["🚀 НАЧАТЬ ПЛАНИРОВАНИЕ"] --> ReadTasks["📚 Читать tasks.md<br>.cursor/rules/isolation_rules/main.mdc"]
    
    %% Complexity Level Determination
    ReadTasks --> CheckLevel{"🧩 Определить<br>уровень сложности"}
    CheckLevel -->|"Уровень 2"| Level2["📝 ПЛАНИРОВАНИЕ УРОВНЯ 2<br>.cursor/rules/isolation_rules/visual-maps/plan-mode-map.mdc"]
    CheckLevel -->|"Уровень 3"| Level3["📋 ПЛАНИРОВАНИЕ УРОВНЯ 3<br>.cursor/rules/isolation_rules/visual-maps/plan-mode-map.mdc"]
    CheckLevel -->|"Уровень 4"| Level4["📊 ПЛАНИРОВАНИЕ УРОВНЯ 4<br>.cursor/rules/isolation_rules/visual-maps/plan-mode-map.mdc"]
    
    %% Level 2 Planning
    Level2 --> L2Review["🔍 Анализ структуры<br>кода"]
    L2Review --> L2Document["📄 Документирование<br>планируемых изменений"]
    L2Document --> L2Challenges["⚠️ Выявление<br>вызовов"]
    L2Challenges --> L2Checklist["✅ Создание чек-листа<br>задач"]
    L2Checklist --> L2Update["📝 Обновление tasks.md<br>с планом"]
    L2Update --> L2Verify["✓ Проверка полноты<br>плана"]
    
    %% Level 3 Planning
    Level3 --> L3Review["🔍 Анализ структуры<br>кодовой базы"]
    L3Review --> L3Requirements["📋 Документирование<br>детальных требований"]
    L3Requirements --> L3Components["🧩 Выявление затронутых<br>компонентов"]
    L3Components --> L3Plan["📝 Создание комплексного<br>плана реализации"]
    L3Plan --> L3Challenges["⚠️ Документирование вызовов<br>и решений"]
    L3Challenges --> L3Update["📝 Обновление tasks.md<br>с планом"]
    L3Update --> L3Flag["🎨 Флаг компонентов,<br>требующих творческий подход"]
    L3Flag --> L3Verify["✓ Проверка полноты<br>плана"]
    
    %% Level 4 Planning
    Level4 --> L4Analysis["🔍 Анализ структуры<br>кодовой базы"]
    L4Analysis --> L4Requirements["📋 Документирование<br>комплексных требований"]
    L4Requirements --> L4Diagrams["📊 Создание архитектурных<br>диаграмм"]
    L4Diagrams --> L4Subsystems["🧩 Выявление затронутых<br>подсистем"]
    L4Subsystems --> L4Dependencies["🔄 Документирование зависимостей<br>и точек интеграции"]
    L4Dependencies --> L4Plan["📝 Создание поэтапного<br>плана реализации"]
    L4Plan --> L4Update["📝 Обновление tasks.md<br>с планом"]
    L4Update --> L4Flag["🎨 Флаг компонентов,<br>требующих творческий подход"]
    L4Flag --> L4Verify["✓ Проверка полноты<br>плана"]
    
    %% Verification & Completion
    L2Verify & L3Verify & L4Verify --> CheckCreative{"🎨 Требуются<br>творческие<br>фазы?"}
    
    %% Mode Transition
    CheckCreative -->|"Да"| RecCreative["⏭️ СЛЕДУЮЩИЙ РЕЖИМ:<br>CREATIVE MODE"]
    CheckCreative -->|"Нет"| RecImplement["⏭️ СЛЕДУЮЩИЙ РЕЖИМ:<br>IMPLEMENT MODE"]
    
    %% Template Selection
    L2Update -.- Template2["ШАБЛОН У2:<br>- Обзор<br>- Файлы для изменения<br>- Шаги реализации<br>- Потенциальные вызовы"]
    L3Update & L4Update -.- TemplateAdv["ШАБЛОН У3-4:<br>- Анализ требований<br>- Затронутые компоненты<br>- Архитектурные соображения<br>- Стратегия реализации<br>- Детальные шаги<br>- Зависимости<br>- Вызовы и смягчения<br>- Компоненты творческой фазы"]
    
    %% Validation Options
    Start -.-> Validation["🔍 ВАРИАНТЫ ВАЛИДАЦИИ:<br>- Анализ уровня сложности<br>- Создание шаблонов планирования<br>- Выявление творческих потребностей<br>- Генерация планировочных документов<br>- Показ перехода режимов"]

    %% Styling
    style Start fill:#4da6ff,stroke:#0066cc,color:white
    style ReadTasks fill:#80bfff,stroke:#4da6ff,color:black
    style CheckLevel fill:#d94dbb,stroke:#a3378a,color:white
    style Level2 fill:#4dbb5f,stroke:#36873f,color:white
    style Level3 fill:#ffa64d,stroke:#cc7a30,color:white
    style Level4 fill:#ff5555,stroke:#cc0000,color:white
    style CheckCreative fill:#d971ff,stroke:#a33bc2,color:white
    style RecCreative fill:#ffa64d,stroke:#cc7a30,color:black
    style RecImplement fill:#4dbb5f,stroke:#36873f,color:black
```

## ШАГИ РЕАЛИЗАЦИИ

### Шаг 1: ЧТЕНИЕ ОСНОВНОГО ПРАВИЛА И ЗАДАЧ
```
read_file({
  target_file: ".cursor/rules/isolation_rules/main.mdc",
  should_read_entire_file: true
})

read_file({
  target_file: "tasks.md",
  should_read_entire_file: true
})
```

### Шаг 2: ЗАГРУЗКА КАРТЫ РЕЖИМА ПЛАНИРОВАНИЯ
```
read_file({
  target_file: ".cursor/rules/isolation_rules/visual-maps/plan-mode-map.mdc",
  should_read_entire_file: true
})
```

### Шаг 3: ЗАГРУЗКА ССЫЛОК НА ПЛАНИРОВАНИЕ ДЛЯ КОНКРЕТНОГО УРОВНЯ СЛОЖНОСТИ
На основе уровня сложности, определенного из tasks.md, загрузить одно из:

#### Для уровня 2:
```
read_file({
  target_file: ".cursor/rules/isolation_rules/Level2/task-tracking-basic.mdc",
  should_read_entire_file: true
})
```

#### Для уровня 3:
```
read_file({
  target_file: ".cursor/rules/isolation_rules/Level3/task-tracking-intermediate.mdc",
  should_read_entire_file: true
})

read_file({
  target_file: ".cursor/rules/isolation_rules/Level3/planning-comprehensive.mdc",
  should_read_entire_file: true
})
```

#### Для уровня 4:
```
read_file({
  target_file: ".cursor/rules/isolation_rules/Level4/task-tracking-advanced.mdc",
  should_read_entire_file: true
})

read_file({
  target_file: ".cursor/rules/isolation_rules/Level4/architectural-planning.mdc",
  should_read_entire_file: true
})
```

## ПОДХОД К ПЛАНИРОВАНИЮ

Создайте детальный план реализации на основе уровня сложности, определенного во время инициализации. Ваш подход должен обеспечивать четкое руководство, оставаясь адаптивным к требованиям проекта и технологическим ограничениям.

### Уровень 2: Планирование простого улучшения

Для задач уровня 2 сосредоточьтесь на создании упрощенного плана, который определяет конкретные необходимые изменения и любые потенциальные вызовы. Проанализируйте структуру кодовой базы, чтобы понять области, затронутые улучшением, и документируйте прямолинейный подход к реализации.

```mermaid
graph TD
    L2["📝 ПЛАНИРОВАНИЕ УРОВНЯ 2"] --> Doc["Документировать план с этими компонентами:"]
    Doc --> OV["📋 Обзор изменений"]
    Doc --> FM["📁 Файлы для изменения"]
    Doc --> IS["🔄 Шаги реализации"]
    Doc --> PC["⚠️ Потенциальные вызовы"]
    Doc --> TS["✅ Стратегия тестирования"]
    
    style L2 fill:#4dbb5f,stroke:#36873f,color:white
    style Doc fill:#80bfff,stroke:#4da6ff,color:black
    style OV fill:#cce6ff,stroke:#80bfff,color:black
    style FM fill:#cce6ff,stroke:#80bfff,color:black
    style IS fill:#cce6ff,stroke:#80bfff,color:black
    style PC fill:#cce6ff,stroke:#80bfff,color:black
    style TS fill:#cce6ff,stroke:#80bfff,color:black
```

### Уровень 3-4: Комплексное планирование

Для задач уровня 3-4 разработайте комплексный план, который затрагивает архитектуру, зависимости и точки интеграции. Выявите компоненты, требующие творческих фаз, и документируйте детальные требования. Для задач уровня 4 включите архитектурные диаграммы и предложите поэтапный подход к реализации.

```mermaid
graph TD
    L34["📊 ПЛАНИРОВАНИЕ УРОВНЯ 3-4"] --> Doc["Документировать план с этими компонентами:"]
    Doc --> RA["📋 Анализ требований"]
    Doc --> CA["🧩 Затронутые компоненты"]
    Doc --> AC["🏗️ Архитектурные соображения"]
    Doc --> IS["📝 Стратегия реализации"]
    Doc --> DS["🔢 Детальные шаги"]
    Doc --> DP["🔄 Зависимости"]
    Doc --> CM["⚠️ Вызовы и смягчения"]
    Doc --> CP["🎨 Компоненты творческой фазы"]
    
    style L34 fill:#ffa64d,stroke:#cc7a30,color:white
    style Doc fill:#80bfff,stroke:#4da6ff,color:black
    style RA fill:#ffe6cc,stroke:#ffa64d,color:black
    style CA fill:#ffe6cc,stroke:#ffa64d,color:black
    style AC fill:#ffe6cc,stroke:#ffa64d,color:black
    style IS fill:#ffe6cc,stroke:#ffa64d,color:black
    style DS fill:#ffe6cc,stroke:#ffa64d,color:black
    style DP fill:#ffe6cc,stroke:#ffa64d,color:black
    style CM fill:#ffe6cc,stroke:#ffa64d,color:black
    style CP fill:#ffe6cc,stroke:#ffa64d,color:black
```

## ВЫЯВЛЕНИЕ ТВОРЧЕСКОЙ ФАЗЫ

```mermaid
graph TD
    CPI["🎨 ВЫЯВЛЕНИЕ ТВОРЧЕСКОЙ ФАЗЫ"] --> Question{"Требует ли компонент<br>дизайнерских решений?"}
    Question -->|"Да"| Identify["Флаг для творческой фазы"]
    Question -->|"Нет"| Skip["Перейти к реализации"]
    
    Identify --> Types["Определить тип творческой фазы:"]
    Types --> A["🏗️ Архитектурный дизайн"]
    Types --> B["⚙️ Дизайн алгоритмов"]
    Types --> C["🎨 UI/UX дизайн"]
    
    style CPI fill:#d971ff,stroke:#a33bc2,color:white
    style Question fill:#80bfff,stroke:#4da6ff,color:black
    style Identify fill:#ffa64d,stroke:#cc7a30,color:black
    style Skip fill:#4dbb5f,stroke:#36873f,color:black
    style Types fill:#ffe6cc,stroke:#ffa64d,color:black
```

Выявите компоненты, которые требуют творческого решения проблем или значительных дизайнерских решений. Для этих компонентов установите флаг для режима CREATIVE. Сосредоточьтесь на архитектурных соображениях, потребностях дизайна алгоритмов или требованиях UI/UX, которые выиграли бы от структурированного исследования дизайна.

## ВЕРИФИКАЦИЯ

```mermaid
graph TD
    V["✅ КОНТРОЛЬНЫЙ СПИСОК ВЕРИФИКАЦИИ"] --> P["План затрагивает все требования?"]
    V --> C["Компоненты, требующие творческих фаз, выявлены?"]
    V --> S["Шаги реализации четко определены?"]
    V --> D["Зависимости и вызовы документированы?"]
    
    P & C & S & D --> Decision{"Все проверено?"}
    Decision -->|"Да"| Complete["Готов к следующему режиму"]
    Decision -->|"Нет"| Fix["Выполнить недостающие элементы"]
    
    style V fill:#4dbbbb,stroke:#368787,color:white
    style Decision fill:#ffa64d,stroke:#cc7a30,color:white
    style Complete fill:#5fd94d,stroke:#3da336,color:white
    style Fix fill:#ff5555,stroke:#cc0000,color:white
```

Перед завершением фазы планирования убедитесь, что все требования затронуты в плане, компоненты, требующие творческих фаз, выявлены, шаги реализации четко определены, и зависимости и вызовы документированы. Обновите tasks.md с полным планом и рекомендуйте подходящий следующий режим на основе того, требуются ли творческие фазы.