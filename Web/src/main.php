<?php
    // Start the session
    session_start();
    $nombre_usuario = $_SESSION['usuario_session'];
?>

<!DOCTYPE html>
<html lang="es">
<head>
    <title>CIIE Lab Remoto</title>
    <?php require('parts/common_header.php') ?>  
</head>
<body>
    <header>
        <h1>Bienvenido</h1>
        <h3>Sistema de gestion de laboratorios remotos</h3>
        <p>Hola, <?php echo "$nombre_usuario"; ?></p>
        <a href="logout.php" class="link-btn">Cerrar Sesión</a>
    </header>

    <main>
        <ul class="semantic-list">
            <li style="margin-block: 20px"><a class="link-btn" href="Labo.php">Laboratorio remoto</a></li>
            <li style="margin-block: 20px"><a class="link-btn" href="#">Mis datos</a></li>
        </ul>
    </main>

    <?php require('parts/common_footer.php') ?>  
</body>
</html>
