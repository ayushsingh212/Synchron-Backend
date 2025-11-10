import nodemailer from "nodemailer"
import dotenv from "dotenv"

// dotenv.config({
//   path:"../../.env"
// })

const transporter = nodemailer.createTransport({
  service: "gmail",
  auth: {
    type: "OAuth2",
    user: process.env.GMAIL_USER,
    clientId: process.env.GMAIL_CLIENT_ID,
    clientSecret: process.env.GMAIL_CLIENT_SECRET,
    refreshToken: process.env.GMAIL_REFRESH_TOKEN,
  },
});

const sendEmail = (email,subject,data)=>{transporter.sendMail({
 from:`"TimeTableScheduler.com" ${""}`,
 to:email,
 subject:subject,
 html:` 
    <h1>TimeTableScheduler.com</h1>
    <h2>Your OTP for verification :<h2>
 
    <h3>    ${data}     </h3>`




})
         
};

export {sendEmail}