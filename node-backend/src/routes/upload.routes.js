import {Router} from "express"
import { getPresignedUploadUrl } from "../controllers/rag.controller.js";


const router = Router()

router.post("/getSignedUrlUpload",getPresignedUploadUrl)



export default router;