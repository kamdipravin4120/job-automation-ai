package com.jobai.companion.core.auth

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.Signature
import javax.inject.Inject
import javax.inject.Singleton

private const val KEY_ALIAS = "jobai_device_key"
private const val PROVIDER = "AndroidKeyStore"

@Singleton
class KeystoreHelper @Inject constructor() {

    private val keyStore = KeyStore.getInstance(PROVIDER).also { it.load(null) }

    val publicKeyHexDer: String
        get() {
            ensureKeyPairExists()
            val entry = keyStore.getEntry(KEY_ALIAS, null) as KeyStore.PrivateKeyEntry
            return entry.certificate.publicKey.encoded.toHexString()
        }

    fun signHex(dataHex: String): String {
        ensureKeyPairExists()
        val entry = keyStore.getEntry(KEY_ALIAS, null) as KeyStore.PrivateKeyEntry
        return Signature.getInstance("Ed25519").run {
            initSign(entry.privateKey)
            update(dataHex.hexToByteArray())
            sign().toHexString()
        }
    }

    fun clearKeyPair() {
        if (keyStore.containsAlias(KEY_ALIAS)) keyStore.deleteEntry(KEY_ALIAS)
    }

    private fun ensureKeyPairExists() {
        if (!keyStore.containsAlias(KEY_ALIAS)) {
            val spec = KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY,
            )
                .setAlgorithmParameterSpec(java.security.spec.ECGenParameterSpec("ed25519"))
                .setDigests(KeyProperties.DIGEST_NONE)
                .build()
            KeyPairGenerator.getInstance("Ed25519", PROVIDER).run {
                initialize(spec)
                generateKeyPair()
            }
        }
    }
}

fun ByteArray.toHexString() = joinToString("") { "%02x".format(it) }
fun String.hexToByteArray() = chunked(2).map { it.toInt(16).toByte() }.toByteArray()
