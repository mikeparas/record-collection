import { Module } from '@nestjs/common';
import { DiscogsService } from './services/discogs.service';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config/dist/config.module';

@Module({
  imports: [HttpModule, ConfigModule],
  providers: [DiscogsService],
  exports: [DiscogsService],
})
export class DiscogsModule {}
