<?php
session_start();

header('Content-Type: application/json; charset=utf-8'); // Cambiado a JSON para consistencia
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

// Detalles de conexión a la base de datos
$servername = getenv("MYSQL_DB_HOST");
$username = getenv("MYSQL_DB_USER");
$password = getenv("MYSQL_DB_PSW");
$dbname = getenv("MYSQL_DB_NAME");
$dbport = getenv("DB_PORT");
$dbConecctionUrl = "pgsql:host=$servername;port=$dbport;dbname=$dbname";

try {
    // Crear conexión con PDO
    $pdo = new PDO($dbConecctionUrl, $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    // Preparar la consulta para obtener el valor de "Accion"
    $stmt = $pdo->prepare("SELECT Accion FROM usuarios WHERE usr_name = :usr_name");

    // Vincular el parámetro
    $action_user = $_SESSION['usuario_session'];
    $stmt->bindParam(':usr_name', $action_user, PDO::PARAM_STR);

    // Ejecutar la consulta
    $stmt->execute();

    // Extraer el valor y enviarlo como JSON
    $row = $stmt->fetch(PDO::FETCH_ASSOC);
    error_log(var_export($row, TRUE));

    if ($row) {
        echo json_encode($row['accion']);
    } else {
        http_response_code(404); // Not Found
        echo json_encode(['error' => "No se encontró la fila 'Accion'"]);
    }
} catch (PDOException $e) {
    http_response_code(500);
    // Asegurarse de que la salida sea JSON válido también en caso de error
    die(json_encode(['error' => 'Error en la base de datos: ' . $e->getMessage()]));
} finally {
    // Cerrar la conexión
    $pdo = null;
}
?>
