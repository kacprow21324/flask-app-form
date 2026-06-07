const databaseName = process.env.MONGO_DATABASE || "ems";
const applicationDatabase = db.getSiblingDB(databaseName);

applicationDatabase.createUser({
  user: process.env.MONGO_APP_USERNAME,
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: [{ role: "readWrite", db: databaseName }],
});
