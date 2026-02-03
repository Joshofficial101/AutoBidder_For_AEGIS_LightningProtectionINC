"""
Financial Calculator for Business Analytics.

Provides methods to calculate profits, margins, and generate business metrics
from job financial data.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


class FinancialCalculator:
    """
    Business logic for financial calculations and analytics.
    """
    
    def __init__(self, job_repo):
        """Initialize with job repository."""
        self.job_repo = job_repo
    
    def calculate_monthly_revenue(
        self,
        user_id: int,
        year: int,
        month: int
    ) -> float:
        """
        Calculate total revenue for a specific month.
        
        Args:
            user_id: ID of the user
            year: Year (e.g., 2026)
            month: Month (1-12)
            
        Returns:
            Total revenue for the month
        """
        # Get date range for month
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        
        # Get jobs completed in this month
        jobs = self.job_repo.get_jobs_by_date_range(user_id, start_date, end_date)
        completed_jobs = [j for j in jobs if j.is_complete]
        
        # Sum bid amounts
        return sum(j.bid_amount or 0 for j in completed_jobs)
    
    def calculate_monthly_profit(
        self,
        user_id: int,
        year: int,
        month: int
    ) -> float:
        """
        Calculate total net profit for a specific month.
        
        Args:
            user_id: ID of the user
            year: Year (e.g., 2026)
            month: Month (1-12)
            
        Returns:
            Total net profit for the month
        """
        # Get date range for month
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        
        # Get jobs completed in this month
        jobs = self.job_repo.get_jobs_by_date_range(user_id, start_date, end_date)
        completed_jobs = [j for j in jobs if j.is_complete]
        
        total_profit = 0
        for job in completed_jobs:
            financials = self.job_repo.get_job_financials(job.job_id)
            if financials and financials.net_profit:
                total_profit += financials.net_profit
        
        return total_profit
    
    def get_monthly_metrics(
        self,
        user_id: int,
        year: int,
        month: int
    ) -> Dict[str, Any]:
        """
        Get comprehensive metrics for a month.
        
        Returns dict with: revenue, profit, profit_margin, jobs_completed, etc.
        """
        revenue = self.calculate_monthly_revenue(user_id, year, month)
        profit = self.calculate_monthly_profit(user_id, year, month)
        
        # Get date range
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        
        jobs = self.job_repo.get_jobs_by_date_range(user_id, start_date, end_date)
        completed_jobs = [j for j in jobs if j.is_complete]
        
        # Calculate costs breakdown
        total_materials = 0
        total_labor = 0
        total_overhead = 0
        
        for job in completed_jobs:
            financials = self.job_repo.get_job_financials(job.job_id)
            if financials:
                total_materials += financials.actual_materials_cost or 0
                total_labor += financials.actual_labor_cost or 0
                total_overhead += financials.overhead_cost or 0
        
        return {
            "revenue": revenue,
            "profit": profit,
            "profit_margin": (profit / revenue * 100) if revenue > 0 else 0,
            "jobs_completed": len(completed_jobs),
            "materials_cost": total_materials,
            "labor_cost": total_labor,
            "overhead_cost": total_overhead,
            "average_profit_per_job": profit / len(completed_jobs) if completed_jobs else 0
        }
    
    def get_ytd_summary(self, user_id: int) -> Dict[str, Any]:
        """Get year-to-date summary."""
        now = datetime.now()
        year = now.year
        
        total_revenue = 0
        total_profit = 0
        
        for month in range(1, now.month + 1):
            total_revenue += self.calculate_monthly_revenue(user_id, year, month)
            total_profit += self.calculate_monthly_profit(user_id, year, month)
        
        return {
            "total_revenue": total_revenue,
            "total_profit": total_profit,
            "profit_margin": (total_profit / total_revenue * 100) if total_revenue > 0 else 0,
            "months": now.month
        }
    
    def get_job_profit_analysis(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get detailed profit analysis for recent jobs.
        
        Returns list of job profit details sorted by completion date.
        """
        # Get completed jobs (simplified - would need better query)
        jobs = self.job_repo.get_active_jobs(user_id)  # This is a simplification
        
        analysis = []
        for job in jobs:
            if not job.is_complete:
                continue
            
            financials = self.job_repo.get_job_financials(job.job_id)
            if not financials:
                continue
            
            analysis.append({
                "project_name": job.project_name,
                "completion_date": job.completion_date,
                "bid_amount": financials.bid_amount,
                "total_costs": financials.total_costs or 0,
                "net_profit": financials.net_profit or 0,
                "profit_margin": financials.profit_margin_pct or 0,
                "materials_variance": (financials.estimated_materials - (financials.actual_materials_cost or 0)),
                "labor_variance": (financials.estimated_labor_cost - (financials.actual_labor_cost or 0))
            })
        
        # Sort by completion date (most recent first)
        analysis.sort(key=lambda x: x["completion_date"] or "", reverse=True)
        
        return analysis[:limit]
