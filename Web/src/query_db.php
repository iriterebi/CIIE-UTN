<?php
error_reporting(E_ALL);
ini_set('display_errors', 1);
header('Content-Type: application/json');
// Database connection details
$servername = getenv("MYSQL_DB_HOST");
$username = getenv("MYSQL_DB_USER");
$password = getenv("MYSQL_DB_PSW");
$dbname = getenv("MYSQL_DB_NAME");

// Crear conexión
$conn = new mysqli($servername, $username, $password, $dbname);

// Verificar conexión
if ($conn->connect_error) {
    die(json_encode(array("error" => "Conexión fallida: " . $conn->connect_error)));
}

// Consulta SQL para obtener datos
$sql = "SELECT * FROM ciie_table";
$result = $conn->query($sql);

// Crear un array para almacenar los datos
$data = array();

if ($result) {
    if ($result->num_rows > 0) {
        // Recorrer los datos y almacenarlos en el array
        while ($row = $result->fetch_assoc()) {
            $data[] = $row;
        }
    }
    $result->close();
} else {
    die(json_encode(array("error" => "Error en la consulta: " . $conn->error)));
}

// Cerrar la conexión
$conn->close();

// Devolver los datos en formato JSON
echo json_encode($data);
?>
