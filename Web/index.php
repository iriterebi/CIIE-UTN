<?php
// Start the session
session_start();
?>
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
        <h3> Sistema de gestion de laboratorios remotos</h3>
    </header>

<!--ENTRE SECCIONES esta como separado-->
    <section class="s1">
        <h2>Ingrese usuario y contraseña</h2>
        <form  class ="styled-form f1" action="log_in.php" method="post">
            <label for="nombre">Nombre de usuario:</label>
            <input  type="text" name="nombre" id="nombre"><br><br>
            <label for="contraseña">Contraseña:</label>
            <input  type="password" name="contraseña" id="contraseña"><br><br>
            <input type="submit" value="Ingresar">
        </form>
         <h3><a href="re.html" >Crear usuario </a></h3> 
    </section> 

    <footer>
        <p>Derechos reservados CIIE - UTN FRBA&copy; </p>
        <p> <h1>La base de datos NO se encuentra encriptada  por el momento y es de dominio publico para los desarrolladores, por este motivo, evitar poner contraseñas reales y/o recurrentes a su persona.</h1></p>

    </footer>
