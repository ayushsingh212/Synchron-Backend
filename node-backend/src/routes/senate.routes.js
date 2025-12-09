import { Router } from "express";
import { senateLogin } from "../controllers/senate.controller.js";



const router = Router();



router.post("/login", senateLogin);


export default router;