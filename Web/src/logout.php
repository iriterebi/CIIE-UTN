<?php
// Iniciar la sesión si aún no se ha iniciado
session_start();

// Destruir la sesión actual
session_destroy();

// Redirigir a la página de inicio de sesión o a otra página, si es necesario
header("Location: index.php"); // Cambia "login.php" por la URL deseada
exit; // Asegúrate de detener la ejecución del script
?>
