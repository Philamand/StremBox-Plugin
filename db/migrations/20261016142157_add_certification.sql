-- migrate:up
ALTER TABLE "public"."users" ADD COLUMN "certification" character varying(255) NULL;

-- migrate:down
ALTER TABLE "public"."users" DROP COLUMN "certification";
