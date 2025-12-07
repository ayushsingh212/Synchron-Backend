import mongooose from "mongoose"


const allotedFacSchema = new mongoose.Schema({

  organisationId:{
    type:mongoose.Schema.Types.ObjectId,
    ref:"Organisation"
  },
  year:{
    type:String,
    trim:true,
  },
    course:{
    type:String,
    trim:true,
  },
    semester:{
    type:String,
    trim:true,
  }
   


},{

})