<?php
session_start();

// Set content type for AJAX response and enable error reporting for debugging
header('Content-Type: application/json; charset=utf-8');
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

// --- Validation ---

// Only allow POST requests
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405); // Method Not Allowed
    echo json_encode(['error' => 'Solo se permiten peticiones POST.']);
    exit;
}

$action = $_POST['action'] ?? null;
$currentUser = $_SESSION['usuario_session'] ?? null;

// Map front-end action names to database ENUM values
$actionMap = [
    'Girar' => 'Girar',
    'Abrir y cerrar pinza' => 'Pinzar',
    'Saludar' => 'Reverencia'
];

// Check for required data
if (!$currentUser) {
    http_response_code(401); // Unauthorized
    echo json_encode(['error' => 'Usuario no autenticado.']);
    exit;
}
if (!isset($actionMap[$action])) {
    http_response_code(400); // Bad Request
    echo json_encode(['error' => 'Acción no válida o no proporcionada.']);
    exit;
}

$dbActionValue = $actionMap[$action];

// --- Database Interaction ---

$servername = getenv("MYSQL_DB_HOST");
$username = getenv("MYSQL_DB_USER");
$password = getenv("MYSQL_DB_PSW");
$dbname = getenv("MYSQL_DB_NAME");
$dbport = getenv("DB_PORT");
$dbConecctionUrl = "pgsql:host=$servername;port=$dbport;dbname=$dbname";
$pdo = null;

try {
    $pdo = new PDO($dbConecctionUrl, $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    $sql = "UPDATE usuarios SET Accion = :action WHERE usr_name = :usr_name";
    $stmt = $pdo->prepare($sql);
    $stmt->bindParam(':usr_name', $currentUser, PDO::PARAM_STR);

    // 1. Set the action
    $stmt->bindParam(':action', $dbActionValue, PDO::PARAM_STR);
    $stmt->execute();

    // usleep(2000000); // Wait for 2 seconds

    // 2. Reset the action to NULL
    // $action_value_reset = null;
    // $stmt->bindParam(':action', $action_value_reset, PDO::PARAM_NULL);
    // $stmt->execute();

    http_response_code(204); // Success, no content to return
} catch (PDOException $e) {
    http_response_code(500); // Internal Server Error
    echo json_encode(['error' => 'Error en la base de datos: ' . $e->getMessage()]);
} finally {
    $pdo = null;
}
