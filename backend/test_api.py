import asyncio
from db.connection import AsyncSessionLocal
from db.models import AdmissionPlan
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AdmissionPlan).filter(AdmissionPlan.ma_nganh == 'TEST-123'))
        print([m.id for m in res.scalars().all()])

asyncio.run(main())
