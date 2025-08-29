<?php
error_reporting(E_ALL);
ini_set('display_errors', 1);
header('Content-Type: application/json');
// Database connection details
$servername = getenv("MYSQL_DB_HOST");
$username = getenv("MYSQL_DB_USER");
$password = getenv("MYSQL_DB_PSW");
$dbname = getenv("MYSQL_DB_NAME");

try {
    // Crear conexión con PDO
    $pdo = new PDO("mysql:host=$servername;dbname=$dbname", $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    // Consulta SQL para obtener datos
    $sql = "SELECT * FROM usuarios";
    $stmt = $pdo->query($sql);

    // Crear un array para almacenar los datos
    $data = $stmt->fetchAll(PDO::FETCH_ASSOC);

    // Devolver los datos en formato JSON
    echo json_encode($data);
} catch (PDOException $e) {
    http_response_code(500);
    die(json_encode(array("error" => "Error en la base de datos: " . $e->getMessage())));
} finally {
    // Cerrar la conexión
    $pdo = null;
}
?>
