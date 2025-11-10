import { compareSync } from "bcrypt";
import mongoose from "mongoose";
import dotenv from "dotenv"


dotenv.config();



const connectDB = async function() {
  
 try {
  console.log("Here are variable",process.env.MONGODB_URL)

const connect = await mongoose.connect(`${process.env.MONGODB_URL}`) 

console.log("The database has been connected successfuly",connect.connection.host)




  
 } catch (error) {
   console.log("MongoDB error ",error)
   process.exit(1)
 }


}
export {connectDB}
