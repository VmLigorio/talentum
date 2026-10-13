// Talentum — mobile/android/build.gradle.kts
// Responsabilidade: configura valores compartilhados pelos módulos Android.
allprojects {
    // Fontes comuns para dependências Android e bibliotecas abertas.
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
// Centraliza as saídas dos módulos no diretório de build compartilhado do app Flutter.
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    // Separa artefatos de cada módulo dentro do diretório de build compartilhado.
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    // Avalia o módulo Android principal antes dos demais módulos gerados pelo Flutter.
    project.evaluationDependsOn(":app")
}

// Desativa lintVital* em todos os subprojetos, inclusive verificações fatais
// do build de release Android (achado 169).
subprojects {
    tasks.configureEach {
        if (name.startsWith("lintVital")) {
            enabled = false
        }
    }
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
