<?php
header('Content-Type: text/plain');  // Especifica que devolveremos texto
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

// Conexión a la base de dato

$servername = getenv("MYSQL_DB_HOST");
$username = getenv("MYSQL_DB_USER");
$password = getenv("MYSQL_DB_PSW");
$dbname = getenv("MYSQL_DB_NAME");

// Crear conexión
$conn = new mysqli($servername, $username, $password, $dbname);


if ($conn->connect_error) {
    die("Conexión fallida: " . $conn->connect_error);
}

// Realizar la consulta para obtener la fila "acciones" en la columna "acciones"
$sql = "SELECT Accion FROM ciie_table WHERE usr_name = 'Accion'"; // Cambia "tu_tabla" por el nombre de tu tabla y "id" por el campo que identifica la fila "acciones"

$result = $conn->query($sql);

// Extraer el valor y enviarlo como JSON
if ($result->num_rows > 0) {
    $fila = $result->fetch_assoc();
    echo json_encode($fila['Accion']); // Aquí enviamos el valor de la columna "acciones"
} else {
    echo json_encode("No se encontró la fila 'Accion'");
}

$conn->close();
?>
