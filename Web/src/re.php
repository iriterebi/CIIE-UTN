<?php
// Start the session
session_start();
?>
<!DOCTYPE html>
<html>
<head>
    <?php require('parts/common_header.php') ?>
    <title>CIIE Lab Remoto</title> <!-- Tab name -->
    <link rel="stylesheet" href="styles/login-form.css">

    <script type="text/javascript">
        function validateForm() {
            var password1 = document.getElementById("contraseña").value;
            var password2 = document.getElementById("r_contraseña").value;

            if (password1 !== password2 || !password1) {
                alert("Passwords do not match or its inexistent. Please re-enter them.");
                return false; // Prevent form submission
            }
            return true; // Allow form submission
        }
    </script>
</head>
<body>
    <header>
        <h1>Bienvenido</h1>
        <h3> Sistema de gestion de laboratorios remotos</h3>
    </header>
    <!-- Sections are separated -->
    <section class="s1">
        <h2>Formulario de registro</h2>
        <form class="f1 login-form" action="reg.php" method="post" onsubmit="return validateForm()">

            <div class="form-field">
                <label slot="label" for="nombre_completo">Nombre y apellio:</label>
                <input slot="input" type="text" name="nombre_completo" id="nombre_completo">
            </div>

            <div class="form-field">
                <label slot="label" for="email">Email de contacto:</label>
                <input slot="input" type="email" name="email" id="email" required>
            </div>

            <div class="form-field">
                <label slot="label" for="nombre">Nombre de usuario:</label>
                <input slot="input" type="text" name="nombre" id="nombre" required>
            </div>

            <div class="form-field">
                <label slot="label" for="contraseña">Contraseña:</label>
                <input slot="input" type="password" name="contraseña" id="contraseña" required>
            </div>

            <div class="form-field">
                <label slot="label" for="r_contraseña">Repetir contraseña:</label>
                <input slot="input" type="password" name="r_contraseña" id="r_contraseña" required>
            </div>

            <div class="form-field">
                <label slot="label" for="pronombres">¿Con qué pronombres te sientes más cómodo/a?</label>
                <input slot="input" type="text" name="pronombres" id="pronombres">
            </div>

            <label>
                <input type="radio" name="status" value="profe"> Soy profesor
                <input type="radio" name="status" value="alumno"> Soy alumno
            </label>
            <br><br> <!-- Create a line break -->
            <input type="submit" value="Registrarme" style="display: inline-block;width: fit-content; margin-top: 0.5rem;">
            <h3><a href="index.php">Volver</a></h3>
        </form>
    </section>
    <footer>
        <p>Derechos reservados CIIE - UTN FRBA&copy;</p>
    </footer>
</body>
</html>
