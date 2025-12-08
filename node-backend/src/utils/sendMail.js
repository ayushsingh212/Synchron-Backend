import nodemailer from "nodemailer"
import dotenv from "dotenv"

// dotenv.config({
//   path:"../../.env"
// })

const transporter = nodemailer.createTransport({
  secure: true,
  host: "smtp.gmail.com",
  port: 465,
  service: "gmail",
  auth: {
    user: process.env.COMP_EMAIL,
    pass: process.env.COMP_PASS,
  },
});

const sendEmail = (email, subject, data, purpose) => {
  const htmlContent = `
  <!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TimeTableScheduler.com - ${purpose}</title>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
      
      * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }
      
      body {
        font-family: 'Poppins', sans-serif;
        line-height: 1.6;
        color: #333;
        background-color: #f8f9fa;
        padding: 20px;
      }
      
      .email-container {
        max-width: 600px;
        margin: 0 auto;
        background: #ffffff;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
        border: 1px solid #eaeaea;
      }
      
      .header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 30px 40px;
        text-align: center;
        color: white;
      }
      
      .logo {
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.5px;
        margin-bottom: 10px;
      }
      
      .logo-subtitle {
        font-size: 14px;
        opacity: 0.9;
        font-weight: 300;
      }
      
      .content {
        padding: 40px;
      }
      
      .purpose-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4edf5 100%);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 32px;
        border-left: 4px solid #667eea;
      }
      
      .purpose-title {
        font-size: 18px;
        color: #2d3748;
        margin-bottom: 8px;
        font-weight: 600;
      }
      
      .purpose-description {
        color: #4a5568;
        font-size: 14px;
      }
      
      .otp-container {
        text-align: center;
        margin: 40px 0;
      }
      
      .otp-label {
        font-size: 16px;
        color: #4a5568;
        margin-bottom: 16px;
        font-weight: 500;
      }
      
      .otp-code {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-size: 36px;
        font-weight: 700;
        padding: 20px 40px;
        border-radius: 12px;
        letter-spacing: 8px;
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
        margin: 10px 0;
      }
      
      .instructions {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 24px;
        margin-top: 32px;
        border-left: 4px solid #48bb78;
      }
      
      .instructions-title {
        font-size: 16px;
        color: #2d3748;
        margin-bottom: 12px;
        font-weight: 600;
      }
      
      .instructions-list {
        list-style: none;
        padding-left: 0;
      }
      
      .instructions-list li {
        padding: 8px 0;
        color: #4a5568;
        font-size: 14px;
        position: relative;
        padding-left: 24px;
      }
      
      .instructions-list li:before {
        content: "✓";
        position: absolute;
        left: 0;
        color: #48bb78;
        font-weight: bold;
      }
      
      .footer {
        text-align: center;
        padding: 30px 40px;
        background: #f8f9fa;
        color: #718096;
        font-size: 13px;
        border-top: 1px solid #eaeaea;
      }
      
      
      .footer-links {
        margin-top: 16px;
      }
      
      .footer-links a {
        color: #667eea;
        text-decoration: none;
        margin: 0 10px;
        font-size: 13px;
      }
      
      .footer-links a:hover {
        text-decoration: underline;
      }
      
      .security-note {
        background: #fff5f5;
        border-radius: 8px;
        padding: 16px;
        margin-top: 24px;
        border-left: 4px solid #fc8181;
      }
      
      .security-title {
        color: #c53030;
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      
      .security-text {
        color: #742a2a;
        font-size: 13px;
        line-height: 1.5;
      }
      
      .highlight {
        background: linear-gradient(120deg, #f0f4ff 0%, #e6f7ff 100%);
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 500;
      }
      
      @media (max-width: 600px) {
        .content, .header, .footer {
          padding: 24px;
        }
        
        .otp-code {
          font-size: 28px;
          padding: 16px 32px;
          letter-spacing: 6px;
        }
      }
    </style>
  </head>
  <body>
    <div class="email-container">
      <div class="header">
        <div class="logo">📅 TimeTableScheduler</div>
        <div class="logo-subtitle">Smart Scheduling Solutions</div>
      </div>
      
      <div class="content">
        <div class="purpose-card">
          <div class="purpose-title">${purpose.charAt(0).toUpperCase() + purpose.slice(1)} Verification</div>
          <div class="purpose-description">
            You are attempting to ${purpose} your TimeTableScheduler account. Please use the OTP below to complete the process.
          </div>
        </div>
        
        <div class="otp-container">
          <div class="otp-label">Your One-Time Password (OTP)</div>
          <div class="otp-code">${data}</div>
          <div style="color: #718096; font-size: 14px; margin-top: 12px;">
            This code will expire in <span class="highlight">10 minutes</span>
          </div>
        </div>
        
        <div class="instructions">
          <div class="instructions-title">How to use this OTP:</div>
          <ul class="instructions-list">
            <li>Enter this OTP in the verification field on our website</li>
            <li>Do not share this code with anyone</li>
            <li>If you didn't request this, please ignore this email</li>
            <li>For security, this OTP is valid for one use only</li>
          </ul>
        </div>
        
        <div class="security-note">
          <div class="security-title">
            <span>🔒 Security Notice</span>
          </div>
          <div class="security-text">
            TimeTableScheduler will never ask for your password or OTP via email, phone, or SMS. 
            This OTP is strictly for ${purpose} verification. Keep it confidential.
          </div>
        </div>
      </div>
      
      <div class="footer">
        <div>© ${new Date().getFullYear()} TimeTableScheduler.com. All rights reserved.</div>
        <div>This is an automated email, please do not reply to this message.</div>
        <div class="footer-links">
          <a href="https://timetablescheduler.com/privacy">Privacy Policy</a>
          <a href="https://timetablescheduler.com/terms">Terms of Service</a>
          <a href="https://timetablescheduler.com/help">Help Center</a>
        </div>
      </div>
    </div>
  </body>
  </html>
  `;

  transporter.sendMail({
    from: `"TimeTableScheduler" <noreply@timetablescheduler.com>`,
    to: email,
    subject: subject,
    html: htmlContent,
    // Add text version for email clients that don't support HTML
    text: `
TimeTableScheduler - ${subject}

${purpose.charAt(0).toUpperCase() + purpose.slice(1)} Verification

Your One-Time Password (OTP): ${data}

This OTP will expire in 10 minutes.

How to use this OTP:
1. Enter this OTP in the verification field on our website
2. Do not share this code with anyone
3. If you didn't request this, please ignore this email
4. For security, this OTP is valid for one use only

Security Notice:
TimeTableScheduler will never ask for your password or OTP via email, phone, or SMS. 
This OTP is strictly for ${purpose} verification. Keep it confidential.

© ${new Date().getFullYear()} TimeTableScheduler.com
This is an automated email, please do not reply.
    `
  }).catch(error => {
    console.error('Error sending email:', error);
    // In production, you might want to log this to a monitoring service
    // e.g., Sentry, Loggly, or your own logging system
  });
};

export {sendEmail}