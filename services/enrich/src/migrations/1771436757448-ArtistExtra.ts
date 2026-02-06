import { MigrationInterface, QueryRunner } from 'typeorm';

export class ArtistExtra1771436757448 implements MigrationInterface {
  name = 'ArtistExtra1771436757448';

  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(
      `CREATE TABLE "app_data"."artist_extra" ("id" uuid NOT NULL, "created_at" TIMESTAMP NOT NULL DEFAULT now(), "updated_at" TIMESTAMP NOT NULL DEFAULT now(), "data" jsonb NOT NULL, CONSTRAINT "PK_13fc401b83e9888769436082201" PRIMARY KEY ("id"))`,
    );
    await queryRunner.query(
      `ALTER TABLE "app_data"."artist_extra" ADD CONSTRAINT "FK_13fc401b83e9888769436082201" FOREIGN KEY ("id") REFERENCES "app_data"."artists"("id") ON DELETE NO ACTION ON UPDATE NO ACTION`,
    );
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(
      `ALTER TABLE "app_data"."artist_extra" DROP CONSTRAINT "FK_13fc401b83e9888769436082201"`,
    );
    await queryRunner.query(`DROP TABLE "app_data"."artist_extra"`);
  }
}
