import groovy.json.JsonSlurper

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// One release identity for PC, ARM and the actual native APK (not just a filename).
val product = JsonSlurper().parse(rootProject.file("../../system/usr/share/oguzdows/product.json")) as Map<*, *>

android {
    namespace = "org.oguzdows.mobile"
    compileSdk = 35
    defaultConfig {
        applicationId = "org.oguzdows.mobile"
        minSdk = 29
        targetSdk = 35
        versionCode = (product["mobile_version_code"] as Number).toInt()
        versionName = product["mobile_version_name"] as String
        buildConfigField("String", "RELEASE_URL", "\"${product["release_url"]}\"")
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true; buildConfig = true }
    testOptions { animationsDisabled = true }
    lint { abortOnError = true }
    sourceSets.getByName("main").assets.srcDir(layout.buildDirectory.dir("generated/bundled-ui"))
    sourceSets.getByName("androidTest").assets.srcDir(layout.buildDirectory.dir("generated/test-assets"))
}

val bundleUi by tasks.registering(Sync::class) {
    val web = rootProject.layout.projectDirectory.dir("../preview/dist")
    from(web)
    into(layout.buildDirectory.dir("generated/bundled-ui"))
    doFirst {
        check(web.file("index.html").asFile.isFile) {
            "Bundled UI missing. Run: cd mobile/preview && npm ci && npm run build"
        }
    }
}
tasks.named("preBuild").configure { dependsOn(bundleUi) }

dependencies {
    implementation("androidx.core:core:1.15.0")
    implementation("androidx.webkit:webkit:1.12.1")
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test:core:1.6.1")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.uiautomator:uiautomator:2.3.0")
}
