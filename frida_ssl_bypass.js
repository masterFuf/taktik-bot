/**
 * Frida script to bypass SSL pinning on Instagram Android app.
 * 
 * Usage:
 *   frida -U -f com.instagram.android -l frida_ssl_bypass.js --no-pause
 * 
 * Or attach to running process:
 *   frida -U com.instagram.android -l frida_ssl_bypass.js
 */

Java.perform(function() {
    console.log("[*] Frida SSL Bypass for Instagram loaded");
    
    // ============================================
    // 1. Bypass OkHttp3 CertificatePinner
    // ============================================
    try {
        var CertificatePinner = Java.use('okhttp3.CertificatePinner');
        
        CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function(hostname, peerCertificates) {
            console.log('[+] OkHttp3 CertificatePinner.check() bypassed for: ' + hostname);
            return;
        };
        
        CertificatePinner.check.overload('java.lang.String', '[Ljava.security.cert.Certificate;').implementation = function(hostname, peerCertificates) {
            console.log('[+] OkHttp3 CertificatePinner.check() bypassed for: ' + hostname);
            return;
        };
        
        console.log('[+] OkHttp3 CertificatePinner hooked');
    } catch (e) {
        console.log('[-] OkHttp3 CertificatePinner not found: ' + e);
    }
    
    // ============================================
    // 2. Bypass OkHttp3 CertificatePinner$Builder
    // ============================================
    try {
        var CertificatePinnerBuilder = Java.use('okhttp3.CertificatePinner$Builder');
        
        CertificatePinnerBuilder.add.overload('java.lang.String', '[Ljava.lang.String;').implementation = function(hostname, pins) {
            console.log('[+] OkHttp3 CertificatePinner.Builder.add() bypassed for: ' + hostname);
            return this;
        };
        
        console.log('[+] OkHttp3 CertificatePinner.Builder hooked');
    } catch (e) {
        console.log('[-] OkHttp3 CertificatePinner.Builder not found: ' + e);
    }
    
    // ============================================
    // 3. Bypass TrustManagerImpl (Android)
    // ============================================
    try {
        var TrustManagerImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
        
        TrustManagerImpl.verifyChain.implementation = function(untrustedChain, trustAnchorChain, host, clientAuth, ocspData, tlsSctData) {
            console.log('[+] TrustManagerImpl.verifyChain() bypassed for: ' + host);
            return untrustedChain;
        };
        
        console.log('[+] TrustManagerImpl hooked');
    } catch (e) {
        console.log('[-] TrustManagerImpl not found: ' + e);
    }
    
    // ============================================
    // 4. Bypass X509TrustManager
    // ============================================
    try {
        var X509TrustManager = Java.use('javax.net.ssl.X509TrustManager');
        var SSLContext = Java.use('javax.net.ssl.SSLContext');
        
        var TrustManager = Java.registerClass({
            name: 'com.taktik.TrustManager',
            implements: [X509TrustManager],
            methods: {
                checkClientTrusted: function(chain, authType) {},
                checkServerTrusted: function(chain, authType) {},
                getAcceptedIssuers: function() { return []; }
            }
        });
        
        var TrustManagers = [TrustManager.$new()];
        var SSLContextInit = SSLContext.init.overload(
            '[Ljavax.net.ssl.KeyManager;',
            '[Ljavax.net.ssl.TrustManager;',
            'java.security.SecureRandom'
        );
        
        SSLContextInit.implementation = function(keyManager, trustManager, secureRandom) {
            console.log('[+] SSLContext.init() - replacing TrustManager');
            SSLContextInit.call(this, keyManager, TrustManagers, secureRandom);
        };
        
        console.log('[+] X509TrustManager hooked');
    } catch (e) {
        console.log('[-] X509TrustManager hook failed: ' + e);
    }
    
    // ============================================
    // 5. Bypass Instagram-specific pinning
    // ============================================
    try {
        // Facebook/Instagram custom SSL pinning
        var classes = [
            'com.facebook.networksecurity.certificatepinning.DefaultCertificatePinnerFactory',
            'com.facebook.networksecurity.certificatepinning.CertificatePinnerFactory',
            'X.0vd',  // Obfuscated class names vary by version
            'X.0ve',
            'X.0vf'
        ];
        
        classes.forEach(function(className) {
            try {
                var clazz = Java.use(className);
                clazz.create.overload().implementation = function() {
                    console.log('[+] ' + className + '.create() bypassed');
                    return null;
                };
            } catch (e) {
                // Class not found, try next
            }
        });
        
        console.log('[+] Instagram-specific pinning hooks attempted');
    } catch (e) {
        console.log('[-] Instagram-specific hooks failed: ' + e);
    }
    
    // ============================================
    // 6. Bypass NetworkSecurityConfig (Android 7+)
    // ============================================
    try {
        var NetworkSecurityConfig = Java.use('android.security.net.config.NetworkSecurityConfig');
        
        NetworkSecurityConfig.isCleartextTrafficPermitted.overload().implementation = function() {
            console.log('[+] NetworkSecurityConfig.isCleartextTrafficPermitted() -> true');
            return true;
        };
        
        NetworkSecurityConfig.isCleartextTrafficPermitted.overload('java.lang.String').implementation = function(hostname) {
            console.log('[+] NetworkSecurityConfig.isCleartextTrafficPermitted(' + hostname + ') -> true');
            return true;
        };
        
        console.log('[+] NetworkSecurityConfig hooked');
    } catch (e) {
        console.log('[-] NetworkSecurityConfig not found: ' + e);
    }
    
    // ============================================
    // 7. Bypass Conscrypt (if used)
    // ============================================
    try {
        var Conscrypt = Java.use('org.conscrypt.Conscrypt');
        var OpenSSLSocketImpl = Java.use('org.conscrypt.OpenSSLSocketImpl');
        
        OpenSSLSocketImpl.verifyCertificateChain.implementation = function(certChain, authMethod) {
            console.log('[+] Conscrypt verifyCertificateChain() bypassed');
        };
        
        console.log('[+] Conscrypt hooked');
    } catch (e) {
        console.log('[-] Conscrypt not found: ' + e);
    }
    
    console.log("[*] SSL Bypass hooks installed successfully");
    console.log("[*] Ready to intercept Instagram traffic");
});
