## Docker Deploy (dev)

Por ahora necesitamos dos shells

### First time using docker
1. Copy .env.example file, change the name to .env and complete it with your db data {Jesus always has the answer, amen}, DO THIS BOTH FOR YOUR .env IN DB AND IN WEB
2. Do this:
```shell
        docker network create ciie-test1
```

### Para la Db
```shell
cd Db && docker compose up
# o puedes corriendolo en segundo plano
cd Db && docker compose up -d

# si es primera vez que se corre la Db habrá que crear las tablas,
# para ello, es necesario correr el siguiente script (en la carpeta Db/)

./migrate.sh
```

### Para el PHP
```shell
cd Web && docker compose up
# o puedes corriendolo en segundo plano
cd Web && docker compose up -d
```
IF you get an error trying to build the web docker, run the following command and then try again...
```shell
docker pull php:8.2-apache-bookworm
```

y luego abrir http://localhost:8080 en el browser para ver la página
