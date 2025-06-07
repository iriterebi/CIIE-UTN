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

// Retrieve data from the HTML form
$nombreCompleto = $_POST["nombre_completo"];
$email = $_POST["email"];
$nombre = $_POST["nombre"];
$contraseña = $_POST["contraseña"];
$rcontraseña = $_POST['r_contraseña'];
$pronombres = $_POST['pronombres'];
$status = $_POST['status'];

try {
    // Check if the user already exists
    $stmt = $pdo->prepare("SELECT * FROM ciie_table WHERE usr_name = :username");
    $stmt->bindParam(':username', $nombre, PDO::PARAM_STR);
    $stmt->execute();

    if ($stmt->rowCount() > 0) {
        echo '<div style="text-align: center; font-size: 24px;">User already exists.</div>';
        echo "<script>
                    setTimeout(function() {
                        window.location.href = 're.html';
                    }, 2000); // Redirect after 3 seconds (adjust as needed)
                  </script>";
    } else {
        // User not found, insert the data
        $sql = "INSERT INTO ciie_table (nombreCompleto,email,usr_name, usr_psw,statuss, usr_pronouns) VALUES (:nombreCompleto,:email,:usr_name, :usr_psw,:statuss,:usr_pronouns)";
        $stmt = $pdo->prepare($sql);
        $stmt->bindParam(':nombreCompleto', $nombreCompleto, PDO::PARAM_STR);
        $stmt->bindParam(':email', $email, PDO::PARAM_STR);
        $stmt->bindParam(':usr_name', $nombre, PDO::PARAM_STR);
        $stmt->bindParam(':usr_psw', $contraseña, PDO::PARAM_STR);
        $stmt->bindParam(':statuss', $status, PDO::PARAM_STR);
        $stmt->bindParam(':usr_pronouns', $pronombres, PDO::PARAM_STR);
        if ($stmt->execute()) {
            echo '<div style="text-align: center; font-size: 24px;">User added.</div>';
            echo "<script>
                        setTimeout(function() {
                            window.location.href = 'index.php';
                        }, 2000); // Redirect after 3 seconds (adjust as needed)
                      </script>";        } else {
            echo "Error adding data to the table: " . $pdo->errorInfo()[4];
        }
    }
} catch (PDOException $e) {
    echo "Error: " . $e->getMessage();
}

// Close the PDO connection
/*
$sql = "SELECT * FROM testing_data WHERE Nombre = '$nombre'";
  /***Chequeo si se borro o tiro error 
if ($conn->query($sql) === TRUE) {
    if ($conn-> > 0) {
        echo "Encontre y borre $conn->affected_rows $nombre ";
    } else {
        echo "Usuario  No encontrado";
    }
} else {
    echo "Error: " . $sql . "<br>" . $conn->error;
}
*************** borrar datos*******************

$sql = "DELETE FROM testing_data WHERE dato1 = 'RRR'";
if ($conn->query($sql) === TRUE) {
    echo "Registro borrado exitosamente.";
} else {
    echo "Error al borrar el registro: " . $conn->error;
}


*************** AGREGAR DATOS*******************

    $sql = "INSERT INTO testing_data (dato1, dato2) VALUES ('$nombre','$contraseña')";
    if ($conn->query($sql) === TRUE) {
        echo "Data added successfully.<br>";
    }
     else {
        echo "Error adding data to the table: " . $conn->error;
    }}
        header("Location:registro.html"); //redirecciona a otra pagina
*/
$pdo = null;
?>
