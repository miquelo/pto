PTO
===

Para preparar el entorno de desarrollo
--------------------------------------

Debes tener las siguientes herramientas en tu sistema:

* [Python 3](https://www.python.org/downloads/) con los módulos
  [docker](https://github.com/docker/docker-py) y
  [paramiko](http://docs.paramiko.org/en/2.2/index.html)
* [Docker Engine](https://store.docker.com/search?type=edition&offering=community)
* [JDK 8](http://www.oracle.com/technetwork/java/javase/downloads/jdk8-downloads-2133151.html)
* [Maven](https://maven.apache.org/download.cgi)

Suponiendo que trabajarás con una configuración llamada `dev`, cada vez que
quieras quieras preparar el entorno actualizado, en el directorio del proyecto
debes ejecutar el comando

```sh
mvn -f module/pto-project/pom.xml install
```

cada vez que este módulo disponga de una nueva versión. Luego

```sh
mvn -f module/pto-all/pom.xml install
```

para instalar los artefactos de la aplicación en el repositorio local, y el
comando

```sh
python3 setup local dev
```

para actualizar el entorno de pruebas.

Si no existe, se creará el fichero `setup.ini` en el directorio del proyecto,
que contiene las propiedades de la configuración. El script pedirá el valor de
las propiedades que no se hayan establecido aún y los almacenará en el fichero
de configuración. Este fichero es ignorado por `git` ya que su contenido es
específico del usuario.

Las propiedades de configuración se pueden modificar manualmente o se pueden
borrar para que el script las vuelva a pedir cuando sea necesario.

Dependencias en desarrollo
--------------------------

Este proyecto depende íntimamente de los proyectos que se listan a continuación.
Se pueden hacer *pull requests* sobre ellos, o bien encontrar la manera de
prescindir de ellos.

* [Docker GlassFish](https://github.com/miquelo/docker-glassfish)
* [JavaEE Toolkit](https://github.com/miquelo/jeetk)

