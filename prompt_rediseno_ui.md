# Prompt Maestro de Rediseño de Interfaz "Voz a Texto" (Grado Producción)

Actúa como un **Experto Senior en UI/UX** y **Arquitecto Frontend en PySide6**. Tu objetivo es realizar un rediseño radical, minimalista, moderno y altamente funcional de la aplicación de escritorio "Voz a Texto". Esta aplicación debe lucir como un producto de nivel comercial (SaaS premium o utilidad nativa moderna del sistema operativo), superando completamente cualquier estética de "prototipo" o diseño rudimentario.

Para lograrlo, consolidarás las mejores prácticas extraídas de las *Skills* de inteligencia de diseño (`ui-ux-pro-max`, `frontend-design`, `pyside-dojutsu`) y aplicarás estrictamente la paleta de colores botánica y terrosa adjunta.

---

## 1. Contexto de la Aplicación y Arquitectura (PySide-Dojutsu)
"Voz a Texto" es una herramienta de dictado global residente en la bandeja del sistema (*system tray*) que utiliza modelos de IA locales (Fast Conformer) para transcribir audio y teclearlo nativamente.
Su ventana principal es [SettingsWindow](file:///home/karlmoz/Documentos/voz-a-texto/backend/voz_a_texto/desktop/settings_window.py#201-468), dividida en una barra lateral (Sidebar) de navegación y un área principal de contenido (*Stacked Widget*). 
**Regla de Oro:** Mantendrás la separación entre lógica y presentación. Si es necesario, abstraerás los componentes visuales personalizados (ej. [ToggleSwitch](file:///home/karlmoz/Documentos/voz-a-texto/backend/voz_a_texto/desktop/settings_window.py#61-87), [HotkeyInput](file:///home/karlmoz/Documentos/voz-a-texto/backend/voz_a_texto/desktop/settings_window.py#27-60)) para que el código sea limpio y altamente mantenible. Usa siempre `Qt.ApplicationAttribute.AA_UseHighDpiPixmaps`.

## 2. Paleta de Colores (Nature & Minimalist Earth-Tones)
Basado en la imagen de referencia, utilizarás variaciones de este esquema terroso y relajante. La interfaz *no debe ser un gris genérico ni un oscuro plano*.

*   **Color 1 (Verde Bosque / Sage Profundo):** `~#406D5E` 
    *(Uso: Fondos de barras laterales en modo oscuro, encabezados, o como color primario de alto énfasis para botones activos).*
*   **Color 2 (Verde Salvia Claro / Menta Suave):** `~#83A990` 
    *(Uso: Acentos sutiles, estados de hover, botones secundarios, y color de los Toggle Switches cuando están activados).*
*   **Color 3 (Marrón Topo / Taupe Cálido):** `~#A8937C` 
    *(Uso: Textos secundarios, estados inactivos, o bordes delicados. Evita usar grises convencionales, usa este color combinado con opacidad).*
*   **Color 4 (Crema / Beige Claro):** `~#E1D8C4` 
    *(Uso: Si haces un Light Theme, será el fondo principal. En un Dark Theme, úsalo para textos de máxima jerarquía o iconos, ofreciendo un contraste suave superior al blanco puro).*

*Nota (Glassmorphism & Contrast):* Ajusta las opacidades (ej. fondo al 10% del Color 1 o 2) para modales o *inputs*, generando profundidad funcional sin saturar.

## 3. Filosofía de Diseño (`ui-ux-pro-max` y `frontend-design`)
1.  **Minimalismo Funcional (Sin Líneas Duras):** Elimina cualquier borde divisor sólido (ej. el borde entre el sidebar y el contenido). Usa el espacio en blanco (*padding/margins* consistentes) para jerarquizar. Define variables o un espaciado consistente: `spacing-sm (8px)`, `spacing-md (16px)`, `spacing-lg (24px)`.
2.  **Glassmorphism Moderado y Sombras:** Añade profundidad a la ventana principal. Sugiero transformar [SettingsWindow](file:///home/karlmoz/Documentos/voz-a-texto/backend/voz_a_texto/desktop/settings_window.py#201-468) en un **FramelessWindowHint** (sin borde nativo del SO), con esquinas perfectamente redondeadas (`border-radius: 12px` general) y una sutil sombra exterior (usando `QGraphicsDropShadowEffect`). Tú dibujarás una pequeña área para arrastrar la ventana.
3.  **Tipografía Proporcional:** Utiliza familias tipográficas modernas y sin remates (ej. `Segoe UI`, `System-UI`, `Inter`). 
    *   Títulos: `20px-24px` semibold.
    *   Cuerpo: `13px-14px` regular.
    *   Labels pequeños: `11px` semibold con *letter-spacing* (MAYÚSCULAS para subtítulos de sección).
4.  **Iconografía SVG Limpia:** ❌ **ESTÁ ESTRICTAMENTE PROHIBIDO USAR EMOJIS COMO ICONOS**. 
    Remueve completamente los emojis de "🖐 General", "⚙ Avanzado", etc. O bien usas SVGs limpios integrados, o aplicas un "maximalismo tipográfico" donde sólo exista el texto perfectamente alineado y estilizado.
5.  **Micro-Interacciones:** Todo botón o área accionable (como el *Sidebar Menu*, el *Toggle Switch* o los botones normales) debe tener:
    *   Cursor de "mano" (`Qt.PointingHandCursor`).
    *   Un cambio claro de color de fondo al hacer `hover` (usando transiciones QSS si es posible).

## 4. Transición de Componentes (Tu Tarea Directa)
Quiero que rescribas completamente el código QSS y la estructura de la clase [SettingsWindow](file:///home/karlmoz/Documentos/voz-a-texto/backend/voz_a_texto/desktop/settings_window.py#201-468) (y sus controles internos como [ToggleSwitch](file:///home/karlmoz/Documentos/voz-a-texto/backend/voz_a_texto/desktop/settings_window.py#61-87) o [FormRow](file:///home/karlmoz/Documentos/voz-a-texto/backend/voz_a_texto/desktop/settings_window.py#88-108)):

*   **El Toggle Switch:** Rediséñalo para que sea más largo y estético (como iOS o Material You). Su color de encendido será el **Verde Salvia Claro** o el **Verde Bosque**, y su *knob* (bolita) no debe estar tocando los bordes abruptamente (crea padding interno coherente).
*   **Botones y Dropdowns (Comboboxes):** Nada debe parecer un control estándar de Windows 95. Los fondos deben ser sutiles (`rgba`), bordes al nivel mínimo visible, y flechas desplegables personalizadas (usando imagen SVG transparente o anulando su renderizado por defecto para pintar uno con `QPainter`).
*   **Sidebar (Barra Lateral):** El fondo aplicará el verde más profundo. El elemento seleccionado se resaltará con un fondo transparente derivado del Color 4 (Beige) a muy pequeña opacidad, y el texto pasará a ser el Beige absoluto con una fuente más pesada.

## 5. Salida Esperada
1.  **Código Python Refactorizado:** Escribe y entrega la versión final de [settings_window.py](file:///home/karlmoz/Documentos/voz-a-texto/backend/voz_a_texto/desktop/settings_window.py) (y de ser necesario extrae piezas a un archivo `theme.py` o similar).
2.  **Calidad de Código:** El script debe ejecutar sin errores, emplear *Type Hints*, y mantener conexiones modernas de *Signals/Slots*.
3.  **Resultado Profesional:** Imagina que el resultado final de esta ventana será el activo visual principal del "landing page" del producto. ¡Haz que haga decir "WOW"!
