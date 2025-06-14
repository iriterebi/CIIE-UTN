<?php
// Database connection parameters
/******************************CONEXION BASICA A BBDD*****************************/
// Database connection details
$servername = getenv("MYSQL_DB_HOST");
$username = getenv("MYSQL_DB_USER");
$password = getenv("MYSQL_DB_PSW");
$dbname = getenv("MYSQL_DB_NAME");


// Crear una conexión a la base de datos
$conn = new mysqli($servername, $username, $password, $dbname);

// Comprobar la conexión
if ($conn->connect_error) {
    die("Conexión fallida: " . $conn->connect_error);
}

// Variables para la actualización
$value = 3; // ID del registro que se actualizará
$usrname = "Accion";

// Consulta SQL para actualizar el registro con un nombre de usuario específico
$sql = "UPDATE ciie_table SET Accion = '$value' WHERE usr_name = '$usrname'";

if ($conn->query($sql) === TRUE) {
    // Redirigir a otra página después de la actualización
    
usleep(2000000);
$value = 0; // ID del registro que se actualizará
$usrname = "Accion";

$sql = "UPDATE ciie_table SET Accion = '$value' WHERE usr_name = '$usrname'";
if ($conn->query($sql) === TRUE) {
    // Redirigir a otra página después de la actualización
    header("Location: Labo.php");
    exit; // Importante: detener la ejecución del script después de redirigir
} else {
    echo "Error al actualizar el registro: " . $conn->error;
}
} else {
    echo "Error al actualizar el registro: " . $conn->error;
}

// Cerrar la conexión a la base de datos
$conn->close();
?>
