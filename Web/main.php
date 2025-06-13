
<!DOCTYPE html>
<html>
<head>
    <title>CIIE Lab Remoto</title> <!--Tab name-->
    <link rel="stylesheet" href="sty_main.css"> <!-- Enlace a un archivo CSS externo -->
    <meta charset="UTF-8">
   
</head>
<body>
    <header>
        <h1>Bienvenido</h1>
        <h3> Sistema de gestion de laboratorios remotos</h>
        <?php
            // OBTENER DATOS DE USUARIO logeado 
            session_start();
            $nombre_usuario = $_SESSION['usuario_session'];
            echo "<p>Hola, $nombre_usuario</p>";
          ?>
       
            <a href="logout.php">Cerrar Sesión</a>
    </header>
    <ul>
        <div style="margin: 20px; padding: 10px;">
            <!-- Your content goes here --> 
             <li><a href="Labo.php">Laboratorio remoto</a></li>
        </div>
        <div style="margin: 20px; padding: 10px;">
            <!-- Your content goes here --> 
             <li><a href="#">Mis datos</a></li>
        </div>

      
        
    </ul>
    <footer>
        <p>Derechos reservados CIIE - UTN FRBA&copy; </p>
    </footer>
</body>
</html>
