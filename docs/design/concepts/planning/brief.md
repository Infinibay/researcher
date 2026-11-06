# Planificación — árbol con detalle

Base07c33eb. Propietario que necesita organizar grupos, consultar hitos y entender
las dependencias, sin confundir una propuesta con trabajo aceptado o ejecutado.
La pantalla anterior fue capturada antes de generar tres conceptos independientes.
Se eligió árbol con detalle y se generó su adaptación móvil con la referencia elegida.
La tabla comprime las explicaciones; el roadmap sugiere una secuencia que los datos
no siempre contienen. Selección delegada explícitamente por el usuario.

Contrato: conservar creación de grupos/hitos y borrado explícito; errores visibles
con borrador conservado; índice aislado por proyecto; consultas independientes de
hitos/tareas/propuestas; dependencias sólo al expandir una tarea conocida; propuestas
con bases, suposiciones y criterios, enlace exacto a la tarea/run originales para
corregir, aceptar o ejecutar. Esta página no crea un segundo protocolo de aceptación.

Ruling: las casillas de las imágenes no se implementan como controles. Un estado
registrado no es aceptación. Se muestran nombres del dominio y estados legibles.
Los controles nativos de decisión permanecen en Tareas y se enlazan conservando
project/task/planRun. Los grupos existentes se consultan con las APIs actuales;
no se sustituyen por un plan sintético ni se ocultan cuando falla otra consulta.

Pruebas: recorrido Chromium con fixturesHTTP, grupos/hitos/eliminación, lectura de
propuestas/dependencias, errores, cambio de proyecto, teclado del diálogo y Axe;
compilación y suitefrontend. No se atribuye a fixtures una validación real de SQLite,
recuperación de escrituras perdidas ni comprensión humana. El endurecimiento del
CRUD antiguo/retirada de imports legacy sigue como tarea principal de engine/operación.
Pulido de densidad/gramática/etiquetas secundarias tras todas las capacidades gruesas.
