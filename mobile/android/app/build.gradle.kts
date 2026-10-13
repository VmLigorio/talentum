// Talentum — mobile/android/app/build.gradle.kts
// Responsabilidade: configura o empacotamento do aplicativo Android.
plugins {
    id("com.android.application")
    id("kotlin-android")
    // O plugin do Flutter depende de os plugins Android e Kotlin já estarem aplicados.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.talentum_mobile"
    compileSdk = flutter.compileSdkVersion
    // Mantém a compatibilidade de bytecode Java e Kotlin no mesmo alvo de execução.
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        // TODO: Definir um identificador exclusivo antes da publicação nas lojas.
        applicationId = "com.example.talentum_mobile"
        // Os SDKs seguem a configuração do Flutter; a biometria exige Android API 24 ou superior.
        minSdk = 24
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // TODO: Configurar chave de assinatura de lançamento antes de distribuir o APK.
            // A chave de depuração mantém o comando de release local funcional durante o desenvolvimento.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

flutter {
    // Aponta o plugin Gradle para a raiz do projeto Flutter que gera este módulo Android.
    source = "../.."
}
