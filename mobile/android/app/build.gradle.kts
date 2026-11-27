plugins { id("com.android.application") }

android {
    namespace = "org.oguzdows.mobile"
    compileSdk = 35
    defaultConfig {
        applicationId = "org.oguzdows.mobile"
        minSdk = 29
        targetSdk = 35
        versionCode = 2
        versionName = "0.2.0-emulator"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    testOptions { animationsDisabled = true }
    lint { abortOnError = true }
    sourceSets.getByName("main").assets.srcDir(layout.buildDirectory.dir("generated/bundled-ui"))
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
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test:core:1.6.1")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.uiautomator:uiautomator:2.3.0")
}
