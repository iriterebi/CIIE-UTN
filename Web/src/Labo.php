<!DOCTYPE html>
<html lang="es">
<head>
    <?php require('parts/common_header.php') ?>  
    <title>CIIE Lab Remoto</title>

    <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js"></script> <!-- jQuery para AJAX -->

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

    <!-- Mostrar el valor actualizado después de ejecutar db_interaction y obtener datos de get_data.php -->
    <?php require('parts/common_footer.php') ?>  

    <script>
        const video = document.getElementById('videoElement');
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ video: true })
            .then(function(stream) {
                video.srcObject = stream;
            })
            .catch(function(error) {
                console.error('Error accessing webcam:', error);
            });
        } else {
            console.error('getUserMedia is not supported by this browser');
        }

        // Función para obtener los datos de get_data.php
        function obtenerAccion() {
            $.ajax({
                url: 'get_data.php',  // Archivo que obtiene el valor de "Accion"
                method: 'GET',
                success: function(response) {
                    // Actualizar el valor mostrado en la página
                    $('#resultado').text(response);
                },
                error: function() {
                    $('#resultado').text('Error al obtener los datos');
                }
            });
        }

        // Manejo del botón "Girar"
        $('#formGirar').on('submit', function(event) {
            event.preventDefault(); // Evita que la página se recargue
            $.post('db_interaction_1.php', function(data) {
                alert('Acción: Girar ejecutada');
                // Luego de ejecutar el script, obtener los datos actualizados
                obtenerAccion();
            });
        });

        // Manejo del botón "Abrir y cerrar pinza"
        $('#formPinza').on('submit', function(event) {
            event.preventDefault(); // Evita que la página se recargue
            $.post('db_interaction_2.php', function(data) {
                alert('Acción: Abrir y cerrar pinza ejecutada');
                // Luego de ejecutar el script, obtener los datos actualizados
                obtenerAccion();
            });
        });

        // Manejo del botón "Saludar"
        $('#formSaludar').on('submit', function(event) {
            event.preventDefault(); // Evita que la página se recargue
            $.post('db_interaction_3.php', function(data) {
                alert('Acción: Saludar ejecutada');
                // Luego de ejecutar el script, obtener los datos actualizados
                obtenerAccion();
            });
        });

        // Llamar a obtenerAccion cuando la página cargue para mostrar el valor actual de "Accion"
        $(document).ready(function() {
            obtenerAccion();  // Mostrar el valor actual de "Accion" al cargar la página
        });
    </script>
</body>
</html>
