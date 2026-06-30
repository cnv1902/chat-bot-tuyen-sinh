import asyncio
from db.connection import AsyncSessionLocal
from db.models import Major
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Major).filter(Major.major_name.ilike("%chăn nuôi%")))
        print([(m.major_code, m.major_name) for m in res.scalars().all()])

asyncio.run(main())
