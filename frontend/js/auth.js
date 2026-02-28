// 1. Import Firebase from CDNs
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import {
    getAuth,
    GoogleAuthProvider,
    signInWithPopup,
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    sendPasswordResetEmail
} from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";
import { getFirestore, doc, setDoc, getDoc } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js";

// 2. Firebase Configuration
const firebaseConfig = {
    apiKey: "AIzaSyC490phLCfByyxbgpfjv804EdtSDjQUin0",
    authDomain: "nivesh-2dff0.firebaseapp.com",
    projectId: "nivesh-2dff0",
    storageBucket: "nivesh-2dff0.firebasestorage.app",
    messagingSenderId: "1098218411997",
    appId: "1:1098218411997:web:7b1a2363ad1d5c56ec0834",
    measurementId: "G-PEKDP4KZZQ"
};

// 3. Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

// 4. Initialize EmailJS
emailjs.init("vsg98k7T7lRE0hSj-");

// 5. UI Elements
const emailInput = document.getElementById("email-input");
const sendOtpBtn = document.getElementById("send-otp-btn");
const otpSection = document.getElementById("otp-section");
const otpInput = document.getElementById("otp-input");
const verifyOtpBtn = document.getElementById("verify-otp-btn");
const googleLoginBtn = document.getElementById("google-login-btn");

// ─── GOOGLE LOGIN ───────────────────────────────────────────────
const provider = new GoogleAuthProvider();

googleLoginBtn.addEventListener("click", async () => {
    try {
        const result = await signInWithPopup(auth, provider);
        await setupUserInFirestore(result.user.uid, result.user.email);
        window.location.href = "dashboard.html";
    } catch (error) {
        console.error("Google Login Error:", error);
        alert("Google Login failed: " + error.message);
    }
});

// ─── OTP SEND ───────────────────────────────────────────────────
sendOtpBtn.addEventListener("click", () => {
    const email = emailInput.value.trim();
    if (!email) return alert("Please enter your email!");

    const generatedOtp = Math.floor(100000 + Math.random() * 900000).toString();

    // Store OTP and email temporarily
    sessionStorage.setItem("secure_otp", generatedOtp);
    sessionStorage.setItem("user_email", email);

    emailjs.send("service_iw9xo6f", "template_yavdxkr", {
        to_email: email,
        otp_code: generatedOtp,
    }).then(() => {
        alert("OTP sent successfully!");
        document.getElementById("email-section").style.display = "none";
        otpSection.style.display = "block";
    }).catch((error) => {
        console.error("EmailJS Error:", error);
        alert("Failed to send OTP. Check EmailJS configuration.");
    });
});

// ─── OTP VERIFY ─────────────────────────────────────────────────
// FIX: Instead of signInAnonymously (which creates a NEW uid every time),
// we use Firebase Email/Password auth with a fixed dummy password.
// This gives the user a PERMANENT, consistent UID tied to their email.
verifyOtpBtn.addEventListener("click", async () => {
    const enteredOtp = otpInput.value.trim();
    const storedOtp = sessionStorage.getItem("secure_otp");
    const userEmail = sessionStorage.getItem("user_email");

    if (enteredOtp !== storedOtp) {
        return alert("Invalid OTP. Please try again.");
    }

    // We use a fixed internal password (user never sees this — OTP is their real auth)
    const internalPassword = "NiveshMitr@" + userEmail.split("@")[0] + "_2024";

    try {
        let userCredential;

        // Try to sign in first (returning user)
        try {
            userCredential = await signInWithEmailAndPassword(auth, userEmail, internalPassword);
            console.log("Existing user signed in.");
        } catch (signInError) {
            // If sign-in fails, the user is new — create their account
            if (signInError.code === "auth/user-not-found" || signInError.code === "auth/invalid-credential" || signInError.code === "auth/invalid-email") {
                userCredential = await createUserWithEmailAndPassword(auth, userEmail, internalPassword);
                console.log("New user account created.");
            } else {
                throw signInError;
            }
        }

        await setupUserInFirestore(userCredential.user.uid, userEmail);
        sessionStorage.removeItem("secure_otp");
        sessionStorage.removeItem("user_email");
        window.location.href = "dashboard.html";

    } catch (error) {
        console.error("Auth Error:", error);
        alert("Login failed: " + error.message);
    }
});

// ─── HELPER: CREATE USER IN FIRESTORE IF NEW ────────────────────
async function setupUserInFirestore(uid, email) {
    const userRef = doc(db, "users", uid);
    const userSnap = await getDoc(userRef);

    if (!userSnap.exists()) {
        await setDoc(userRef, {
            email: email,
            cashBalance: 1000000,
            createdAt: new Date().toISOString()
        });
        console.log("New profile created! ₹10,00,000 added to wallet.");
    } else {
        console.log("Welcome back,", email);
    }
}