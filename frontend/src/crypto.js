// Cryptographic utilities using Web Crypto API
// implements ECDH for key exchange and AES-GCM for encryption

export async function generateKeyPair() {
    return await window.crypto.subtle.generateKey(
        {
            name: "ECDH",
            namedCurve: "P-256",
        },
        false, // not extractable (we only export public key)
        ["deriveKey"]
    );
}

export async function exportPublicKey(key) {
    const exported = await window.crypto.subtle.exportKey("spki", key);
    return btoa(String.fromCharCode(...new Uint8Array(exported)));
}

export async function importPublicKey(spkiBase64) {
    const binary = atob(spkiBase64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return await window.crypto.subtle.importKey(
        "spki",
        bytes.buffer,
        {
            name: "ECDH",
            namedCurve: "P-256",
        },
        true,
        []
    );
}

export async function deriveSharedKey(privateKey, publicKey) {
    return await window.crypto.subtle.deriveKey(
        {
            name: "ECDH",
            public: publicKey,
        },
        privateKey,
        {
            name: "AES-GCM",
            length: 256,
        },
        false,
        ["encrypt", "decrypt"]
    );
}

export async function encryptMessage(key, text) {
    const encoder = new TextEncoder();
    const data = encoder.encode(text);
    const iv = window.crypto.getRandomValues(new Uint8Array(12));
    const encrypted = await window.crypto.subtle.encrypt(
        {
            name: "AES-GCM",
            iv: iv,
        },
        key,
        data
    );

    return {
        content: btoa(String.fromCharCode(...new Uint8Array(encrypted))),
        iv: btoa(String.fromCharCode(...iv)),
    };
}

export async function decryptMessage(key, encryptedData, ivBase64) {
    const binaryEnc = atob(encryptedData);
    const bytesEnc = new Uint8Array(binaryEnc.length);
    for (let i = 0; i < binaryEnc.length; i++) {
        bytesEnc[i] = binaryEnc.charCodeAt(i);
    }

    const binaryIv = atob(ivBase64);
    const bytesIv = new Uint8Array(binaryIv.length);
    for (let i = 0; i < binaryIv.length; i++) {
        bytesIv[i] = binaryIv.charCodeAt(i);
    }

    try {
        const decrypted = await window.crypto.subtle.decrypt(
            {
                name: "AES-GCM",
                iv: bytesIv,
            },
            key,
            bytesEnc.buffer
        );
        const decoder = new TextDecoder();
        return decoder.decode(decrypted);
    } catch (err) {
        console.error("Decryption failed", err);
        return "[Decryption Error]";
    }
}
