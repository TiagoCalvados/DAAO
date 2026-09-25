import java.util.Properties

plugins {
    id("com.android.application")
}

val defaultSigningPropertiesFile = System.getenv("LOCALAPPDATA")
    ?.let { file("$it/DAAO/android-signing/keystore.properties") }
val signingPropertiesFile = providers.gradleProperty("daaoSigningProperties")
    .orElse(providers.environmentVariable("DAAO_SIGNING_PROPERTIES"))
    .orNull
    ?.let(::file)
    ?: defaultSigningPropertiesFile
val signingProperties = Properties().apply {
    if (signingPropertiesFile?.isFile == true) {
        signingPropertiesFile.inputStream().use(::load)
    }
}
val releaseSigningAvailable = listOf(
    "storeFile",
    "storePassword",
    "keyAlias",
    "keyPassword",
).all { !signingProperties.getProperty(it).isNullOrBlank() } &&
    signingProperties.getProperty("storeFile")?.let { file(it).isFile } == true

if (gradle.startParameter.taskNames.any { it.contains("release", ignoreCase = true) }) {
    check(releaseSigningAvailable) {
        "Release signing requires a valid keystore.properties file. " +
            "Set DAAO_SIGNING_PROPERTIES or -PdaaoSigningProperties."
    }
}

android {
    namespace = "com.tiagocalvados.daao"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.tiagocalvados.daao"
        minSdk = 23
        targetSdk = 36
        versionCode = 403
        versionName = "0.4.3"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        if (releaseSigningAvailable) {
            create("release") {
                storeFile = file(signingProperties.getProperty("storeFile"))
                storePassword = signingProperties.getProperty("storePassword")
                keyAlias = signingProperties.getProperty("keyAlias")
                keyPassword = signingProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        create("tiago") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".tiago"
            signingConfig = signingConfigs.getByName("debug")
            matchingFallbacks += listOf("debug")
        }
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    sourceSets.getByName("tiago").assets.srcDir(rootProject.file("../.private/android-assets"))

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    add("tiagoImplementation", files(rootProject.file("../.private/runtime/sherpa-onnx-1.13.8.aar")))
    implementation("androidx.activity:activity-ktx:1.13.0")
    implementation("androidx.camera:camera-camera2:1.6.1")
    implementation("androidx.camera:camera-core:1.6.1")
    implementation("androidx.camera:camera-lifecycle:1.6.1")
    implementation("androidx.camera:camera-view:1.6.1")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20260719")
}
