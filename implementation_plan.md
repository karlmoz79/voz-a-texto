# Rediseño de Interfaz "Voz a Texto" - Implementation Plan

**Goal:** Transformar la aplicación de escritorio a un diseño premium, minimalista y terroso usando PySide6, eliminando el aspecto "prototipo".

## User Review Required

- **Frameless Window**: Estamos cambiando la ventana a `FramelessWindowHint`, lo que significa que el borde nativo del SO desaparecerá, y dibujaremos una barra de arrastre personalizada en su lugar. ¿Está bien esto para tu flujo de trabajo en Linux?
- **Iconografía**: Reemplazaremos los emojis del sidebar por texto limpio para mantener el "maximalismo tipográfico" minimalista.

## Proposed Changes

### UI Theme y Refactorización

Separaremos las constantes visuales del código lógico para respetar el principio de separación de responsabilidades y aplicaremos los estilos requeridos.

#### [NEW] [theme.py](file:///home/karlmoz/Documentos/voz-a-texto/backend/voz_a_texto/desktop/theme.py)
- Creado para albergar constantes de color: `COLOR_FOREST_GREEN (#406D5E)`, `COLOR_SAGE_LIGHT (#83A990)`, `COLOR_TAUPE (#A8937C)`, `COLOR_CREAM (#E1D8C4)` y sus variantes con opacidad.
- Exportar el `STYLESHEET` unificado usando tipografía moderna (`Segoe UI, Inter`) y eliminando bordes duros.

#### [MODIFY] [settings_window.py](file:///home/karlmoz/Documentos/voz-a-texto/backend/voz_a_texto/desktop/settings_window.py)
- Importar `theme.py` y aplicar estilos globales.
- Convertir [SettingsWindow](file:///home/karlmoz/Documentos/voz-a-texto/backend/voz_a_texto/desktop/settings_window.py#201-468) a usar `Qt.WindowType.FramelessWindowHint`.
- Implementar un área interactiva para poder arrastrar la ventana (eventos `mousePressEvent` y `mouseMoveEvent`).
- Aplicar `QGraphicsDropShadowEffect` y bordes redondeados (`border-radius: 12px` usando path clipping o una ventana base transparente).
- **ToggleSwitch**: Rediseñar la bolita y el fondo para que luzca como iOS/Material. Fondo de encendido será `COLOR_SAGE_LIGHT` o `COLOR_FOREST_GREEN`.
- **Sidebar**: Eliminar emojis (`"🖐 General" -> "General"`, etc.). Aplicar fondo `COLOR_FOREST_GREEN`. El item seleccionado tendrá texto `COLOR_CREAM` y fondo `rgba` transparente derivado de `COLOR_CREAM`.
- **Inputs & Dropdowns**: Cambiar fondos a semitransparentes sutiles con hover effect. Cambiar los íconos del combo box (`QComboBox::down-arrow`).

## Verification Plan

### Manual Verification
1. Ejecutar el script nativo local de UI desde la terminal: `cd /home/karlmoz/Documentos/voz-a-texto/backend && uv run python scripts/desktop_app.py`.
2. Verificar visualmente:
   - Que la ventana no tenga el borde clásico del SO.
   - Porder arrastrar la ventana desde una zona libre superior.
   - Pasar el cursor sobre el menú lateral y verificar el cursor tipo "mano" (`Qt.PointingHandCursor`) y la transición suave a Beige.
   - Activar y desactivar el switch de "Dictado nativo". El *knob* no debe chocar con los bordes abruptamente y el encendido debe ser color Salvia/Menta.
   - Abrir y cerrar el desplegable de "Modelo Activo" para ver el nuevo diseño QSS (sin aspecto "Windows 95").
   - Comprobar que no hay uso de emojis y domina la fuente Sans-Serif limpia recomendada en todo el cuerpo.
