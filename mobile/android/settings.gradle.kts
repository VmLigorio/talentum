// Talentum — mobile/android/settings.gradle.kts
// Responsabilidade: registra plugins e módulos usados pelo build Android.
pluginManagement {
    // Lê o caminho do SDK Flutter local para incluir os plugins fornecidos pelo próprio SDK.
    val flutterSdkPath =
        run {
            val properties = java.util.Properties()
            file("local.properties").inputStream().use { properties.load(it) }
            val flutterSdkPath = properties.getProperty("flutter.sdk")
            require(flutterSdkPath != null) { "flutter.sdk not set in local.properties" }
            flutterSdkPath
        }

    // Disponibiliza o plugin Gradle do Flutter antes de avaliar os módulos Android.
    includeBuild("$flutterSdkPath/packages/flutter_tools/gradle")

    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }

    resolutionStrategy {
        eachPlugin {
            if (requested.id.id == "org.jetbrains.kotlin.android") {
                // Mantém a resolução do plugin Kotlin na versão alinhada ao toolchain Flutter/Android.
                useModule("org.jetbrains.kotlin:kotlin-gradle-plugin:2.2.20")
            }
        }
    }
}

plugins {
    // Carrega o módulo Flutter e declara as versões dos plugins aplicados pelo módulo app.
    id("dev.flutter.flutter-plugin-loader") version "1.0.0"
    id("com.android.application") version "8.11.1" apply false
    id("org.jetbrains.kotlin.android") version "2.2.20" apply false
}

// Inclui o único módulo instalável deste projeto Android.
include(":app")
