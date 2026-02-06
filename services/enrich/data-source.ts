import "reflect-metadata"
import dotenv from "dotenv"

import { DataSource, DataSourceOptions } from "typeorm";

dotenv.config({path: "../../.env"});

export default new DataSource({
    type: "postgres",
    database: process.env.DB_NAME || "",
    host: process.env.DB_HOST || "localhost",
    port: parseInt(process.env.DB_PORT || "5432"),
    // admin for migrations
    username: process.env.DB_ADMIN_USER || "",
    password: process.env.DB_ADMIN_PASS || "",
    schema: process.env.DB_SCHEMA || "",
    entities: [
        "src/**/*.entity.ts"
    ],

    synchronize: false,

    migrationsRun: false,
    migrations: ["src/migrations/*.ts"],
    migrationsTableName: "migrations_typeorm"
});