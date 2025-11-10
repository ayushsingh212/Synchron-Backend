class ApiError extends Error {

constructor(
  statusCode,
  message = "The operation has been failed",
  errors = [],
  stack = ""


)
{
  super(message)

  this.message = message;
  this.success = false;
  this.errors = errors;
  this.statusCode = statusCode;
  this.data = null


 if(stack)
 {
  this.stack =stack
 }
else
{
 

  this.stack =  Error.captureStackTrace(this,this.constructor)


}







}





}

export default ApiError;