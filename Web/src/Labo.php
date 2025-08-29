<!DOCTYPE html>
<html lang="es">
<head>
    <?php require('parts/common_header.php') ?>
    <title>CIIE Lab Remoto</title>

    <style>
        /* Estilos para el header fijo */
        header {
            position: sticky;
            top: 0;
            left: 0;
            width: 100%;
            padding: 10px 0;
            z-index: 1000;
            text-align: center;
            box-shadow: 0 4px 2px -2px gray;
        }

        header a {
            margin: 0 20px;
            text-decoration: none;
            color: #333;
            font-weight: bold;
            font-size: 18px;
        }

        header h1, header p {
            margin: 0;
            padding: 0;
        }

        /* Contenedor de la cámara y los controles */
        .container {
            display: flex;
            flex-direction: row; /* Colocar los elementos en fila */
            justify-content: space-between; /* Separar los elementos dentro del contenedor */
            align-items: flex-start; /* Alinear los elementos al principio */
            padding: 20px;
            margin-top: 100px; /* Dejar espacio para el header */
        }

        /* Sección de controles */
        .controls {
            display: flex;
            flex-direction: column;
            align-items: center; /* Centrar los botones horizontalmente */
            justify-content: center; /* Centrar verticalmente */
            width: 30%; /* Ajustar el ancho de la columna de controles */
        }

        .f1 {
            margin: 20px;
        }

        input[type="submit"] {
            padding: 15px 40px;
            font-size: 18px;
            cursor: pointer;
            border: 2px solid #4CAF50;
            background-color: #4CAF50;
            color: white;
            border-radius: 5px;
            transition: background-color 0.3s ease;
            display: inline-block;
            width: auto;
        }

        input[type="submit"]:hover {
            background-color: #45a049;
            border-color: #45a049;
        }

        /* Sección de la cámara */
        .camera {
            width: 65%; /* Ajustar el ancho de la columna de la cámara */
            display: flex;
            justify-content: center; /* Centrar la cámara */
            align-items: center;
        }

        video {
            max-width: 90%; /* Reducir el ancho máximo del video */
            height: auto; /* Mantener la proporción del video */
            border: 2px solid #333; /* Agregar un borde al video */
            border-radius: 10px;
        }

    </style>
</head>
<body>
    <header>
        <h1>Bienvenido</h1>
        <p><h3>Sistema de gestión de laboratorios remotos</h3></p>
        <!-- BTN MENU -->
        <a href="main.php">Menú principal</a>
        <!-- BTN CERRAR SESION -->
        <a href="logout.php">Cerrar sesión</a>
    </header>

    <!-- Contenedor de controles y cámara -->
    <div class="container">
        <!-- Sección de controles -->
        <div class="controls">
            <h2>Controles</h2>

            <!-- BOTÓN "Girar" -->
            <form class="f1" id="formGirar">
                <input type="submit" value="Girar">
            </form>

            <!-- BOTÓN "Abrir y cerrar pinza" -->
            <form class="f1" id="formPinza">
                <input type="submit" value="Abrir y cerrar pinza">
            </form>

            <!-- BOTÓN "Saludar" -->
            <form class="f1" id="formSaludar">
                <input type="submit" value="Saludar">
            </form>
        </div>

        <!-- Sección de la cámara -->
        <div class="camera">
            <video id="videoElement" autoplay></video>
        </div>
    </div>

    <!-- Elemento para mostrar la acción actual. Se agregó porque el script original intentaba usarlo pero no existía. -->
    <div id="resultado" style="text-align: center; margin: 20px; font-weight: bold;"></div>

    <?php require('parts/common_footer.php') ?>

    <script>
        "use strict";
        document.addEventListener('DOMContentLoaded', () => {
            const video = document.getElementById('videoElement');
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({ video: true })
                .then(function(stream) {
                    video.srcObject = stream;
                })
                .catch(function(error) {
                    console.error('Error al acceder a la cámara:', error);
                });
            } else {
                console.error('getUserMedia no es soportado por este navegador');
            }

            const resultadoEl = document.getElementById('resultado');

            // Función para obtener los datos de get_data.php usando Fetch API
            async function obtenerAccion() {
                try {
                    const response = await fetch('get_data.php');
                    if (!response.ok) {
                        throw new Error(`Error de red: ${response.statusText}`);
                    }
                    const data = await response.json(); // get_data.php devuelve JSON
                    if (resultadoEl) {
                        resultadoEl.textContent = `Última acción registrada: ${data || 'Ninguna'}`;
                    }
                } catch (error) {
                    console.error('Error al obtener los datos:', error);
                    if (resultadoEl) {
                        resultadoEl.textContent = 'Error al obtener los datos';
                    }
                }
            }

            // Función genérica para manejar los envíos de formularios de acción
            function setupActionForm(formId, actionName) {
                const form = document.getElementById(formId);
                if (form) {
                    form.addEventListener('submit', async (event) => {
                        event.preventDefault(); // Evita que la página se recargue
                        try {
                            const response = await fetch('action_handler.php', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/x-www-form-urlencoded',
                                },
                                body: new URLSearchParams({
                                    'action': actionName
                                })
                            });

                            if (!response.ok && response.status !== 204) { // 204 es éxito sin contenido
                                const errorData = await response.json();
                                throw new Error(errorData.error || `Error del servidor: ${response.statusText}`);
                            }

                            alert(`Acción: ${actionName} ejecutada`);
                            obtenerAccion();
                        } catch (error) {
                            console.error(`Error en la acción ${actionName}:`, error);
                            alert(`Error al ejecutar la acción ${actionName}: ${error.message}`);
                        }
                    });
                }
            }

            // Configurar los manejadores de eventos para cada botón
            setupActionForm('formGirar', 'Girar');
            setupActionForm('formPinza', 'Abrir y cerrar pinza');
            setupActionForm('formSaludar', 'Saludar');

            // Llamar a obtenerAccion cuando la página cargue para mostrar el valor actual de "Accion"
            obtenerAccion();
        });
    </script>
</body>
</html>
