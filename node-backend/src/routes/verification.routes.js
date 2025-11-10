import {Router} from "express"
import { sendOTP } from "../controllers/verification.controller.js";


const router = Router();


router.post("/getOtp",sendOTP);



export default router;