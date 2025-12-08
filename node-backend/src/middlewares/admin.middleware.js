import jwt from "jsonwebtoken";
import ApiError from "../utils/apiError.js";

export const verifyAdminToken = (req, res, next) => {
  const token =  req.cookies.adminToken ||  req.headers.authorization?.split(" ")[1];
  if (!token) throw new ApiError(401, "Admin token required");

  try {
    const decoded = jwt.verify(token, process.env.ADMIN_TOKEN_SECRET);
    if (decoded.type !== "ADMIN") throw new ApiError(403, "Not an admin");
    req.admin = decoded;
    next();
  } catch (err) {
    throw new ApiError(401, "Invalid admin token");
  }
};
