// 1. Import Firebase from CDNs
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signInAnonymously } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";
import { getFirestore, doc, setDoc, getDoc } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js";

// 2. Firebase Configuration (Replace with your actual keys from Firebase Console)
const firebaseConfig = {
    apiKey: "AIzaSyC490phLCfByyxbgpfjv804EdtSDjQUin0",
  authDomain: "nivesh-2dff0.firebaseapp.com",
  projectId: "nivesh-2dff0",
  storageBucket: "nivesh-2dff0.firebasestorage.app",
  messagingSenderId: "1098218411997",
  appId: "1:1098218411997:web:7b1a2363ad1d5c56ec0834",
  measurementId: "G-PEKDP4KZZQ"
};

// 3. Initialize Firebase & Services
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

// 4. Initialize EmailJS (Replace with your public key)
emailjs.init("vsg98k7T7lRE0hSj-");

// 5. Connect UI Elements
const emailInput = document.getElementById("email-input");
const sendOtpBtn = document.getElementById("send-otp-btn");
const otpSection = document.getElementById("otp-section");
const otpInput = document.getElementById("otp-input");
const verifyOtpBtn = document.getElementById("verify-otp-btn");
const googleLoginBtn = document.getElementById("google-login-btn");

// --- GOOGLE LOGIN LOGIC ---
const provider = new GoogleAuthProvider();

googleLoginBtn.addEventListener("click", async () => {
    try {
        const result = await signInWithPopup(auth, provider);
        await setupUserInFirestore(result.user.uid, result.user.email);
        window.location.href = "dashboard.html"; // Send to dashboard on success
    } catch (error) {
        console.error("Google Login Error:", error);
        alert("Google Login failed. Check console.");
    }
});

// --- EMAIL + OTP LOGIC ---
sendOtpBtn.addEventListener("click", () => {
    const email = emailInput.value;
    if (!email) {
        alert("Please enter an email!");
        return;
    }

    // Generate a random 6-digit OTP
    const generatedOtp = Math.floor(100000 + Math.random() * 900000).toString();
    
    // Save to the browser's temporary storage securely
    sessionStorage.setItem("secure_otp", generatedOtp);
    sessionStorage.setItem("user_email", email);

    // Send Email via EmailJS (Replace Service ID and Template ID)
    emailjs.send("service_iw9xo6f", "template_yavdxkr", {
        to_email: email,
        otp_code: generatedOtp,
    }).then(() => {
        alert("OTP sent successfully!");
        document.getElementById("email-section").style.display = "none";
        otpSection.style.display = "block"; // Show the OTP input box
    }).catch((error) => {
        console.error("EmailJS Error:", error);
        alert("Failed to send OTP.");
    });
});

verifyOtpBtn.addEventListener("click", async () => {
    const enteredOtp = otpInput.value;
    const storedOtp = sessionStorage.getItem("secure_otp");
    const userEmail = sessionStorage.getItem("user_email");

    if (enteredOtp === storedOtp) {
        try {
            // Login anonymously to Firebase to get a secure UID
            const result = await signInAnonymously(auth);
            
            // Link the email to the UID and give them ₹1,000,000
            await setupUserInFirestore(result.user.uid, userEmail);
            
            sessionStorage.removeItem("secure_otp"); // Clean up for security
            window.location.href = "dashboard.html"; // Send to dashboard on success
        } catch (error) {
            console.error("Auth Error:", error);
        }
    } else {
        alert("Invalid OTP. Please try again.");
    }
});

// --- HELPER FUNCTION: DATABASE SETUP ---
// This checks if the user is new. If yes, it creates their document and adds the starting balance.
async function setupUserInFirestore(uid, email) {
    const userRef = doc(db, "users", uid);
    const userSnap = await getDoc(userRef);
    
    if (!userSnap.exists()) {
        await setDoc(userRef, {
            email: email,
            cashBalance: 1000000,
            createdAt: new Date()
        });
        console.log("New account created! ₹1,000,000 added to wallet.");
    } else {
        console.log("Existing user logged in.");
    }
}