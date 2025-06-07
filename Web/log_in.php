<?php
session_start();

/******************************CONEXION BASICA A BBDD*****************************/
// Database connection details
$servername = "db:3306";
$username = "debian-sys-maint";
$password = "olga123";
$dbname = "ciie_db"; // Cambia al nombre de tu base de datos MySQL

try {
    // Create a PDO connection
    $pdo = new PDO("mysql:host=$servername;dbname=$dbname", $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (PDOException $e) {
    die("Connection failed: " . $e->getMessage());
}
/***********************************************************/
//Check how infinityFree connects 2 php and db, how to get mySQL running,maybe its a credential thing or a innit thing


// Retrieve data from the HTML form
$nombre = $_POST["nombre"];
$contraseña = $_POST["contraseña"];
try {
    // Select the password for the specified user
    $stmt = $pdo->prepare("SELECT usr_psw FROM ciie_table WHERE usr_name = :username");
    $stmt->bindParam(':username', $nombre, PDO::PARAM_STR);
    $stmt->execute();

    $row = $stmt->fetch(PDO::FETCH_ASSOC);

    if ($row) {
        $password = $row['usr_psw'];
        if ($password == $contraseña) {
            echo '<div style="text-align: center; font-size: 24px;">Contraseña correcta</div>';

            // Iniciar la sesión
            $_SESSION['usuario_session'] = $nombre; // Almacena el nombre de usuario
            $_SESSION['authenticated'] = true; // Marca al usuario como autenticado
            
            header("Location: main.php"); // Redirecciona a otra página
        } else {
            echo '<div style="text-align: center; font-size: 24px;">Contraseña incorrecta</div>';
            echo "<script>
            setTimeout(function() {
                window.location.href = 'index.php';
            }, 2000); // Redirecciona después de 3 segundos (ajusta según sea necesario)
          </script>";
        }
    } else {
        echo "Usuario '$nombre' no encontrado.";
    }
} catch (PDOException $e) {
    echo "Error: " . $e->getMessage();
}
$pdo = null;
?>
