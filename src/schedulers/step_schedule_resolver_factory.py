from fpml.confirmation import InterestRateStream
from src.schedulers.reference_resolver import ReferenceResolver
from src.schedulers.step_schedule_resolver import StepScheduleResolver


class StepScheduleResolverFactory:
    """InterestRateStream に定義された各種ステップスケジュールから
    StepScheduleResolver インスタンスを一括生成し、保持するファクトリ兼コンテナクラス。
    """

    def __init__(self, stream: InterestRateStream, ref_resolver: ReferenceResolver):
        self._ref_resolver = ref_resolver
        calc_params = stream.calculation_period_amount.calculation

        # 各リゾルバーを初期設定
        self.notional_resolver = self._create_notional_resolver(calc_params)
        self.fixed_rate_resolver = self._create_fixed_rate_resolver(calc_params)

        self.spread_resolver = self._create_spread_resolver(calc_params)
        self.multiplier_resolver = self._create_multiplier_resolver(calc_params)

    def _create_notional_resolver(self, calc_params) -> StepScheduleResolver:
        if calc_params.fx_linked_notional_schedule is not None:
            return StepScheduleResolver(None)

        notional_schedule = calc_params.notional_schedule
        if notional_schedule is None:
            return StepScheduleResolver(None)

        step_schedule = None
        if notional_schedule.notional_step_schedule is not None:
            step_schedule = notional_schedule.notional_step_schedule
        elif notional_schedule.notional_step_parameters_reference is not None:
            step_schedule = self._ref_resolver.resolve(
                notional_schedule.notional_step_parameters_reference
            )

        return StepScheduleResolver(step_schedule)

    def _create_fixed_rate_resolver(self, calc_params) -> StepScheduleResolver:
        fixed_rate_schedule = calc_params.fixed_rate_schedule
        return StepScheduleResolver(fixed_rate_schedule)

    def _create_spread_resolver(self, calc_params) -> StepScheduleResolver:
        floating_rate_calc = calc_params.floating_rate_calculation
        if floating_rate_calc is None:
            return StepScheduleResolver(None)

        spread_schedule = (
            floating_rate_calc.spread_schedule[0]
            if floating_rate_calc.spread_schedule
            else None
        )
        return StepScheduleResolver(spread_schedule)

    def _create_multiplier_resolver(self, calc_params) -> StepScheduleResolver:
        floating_rate_calc = calc_params.floating_rate_calculation
        if floating_rate_calc is None:
            return StepScheduleResolver(None)

        multiplier_schedule = (
            floating_rate_calc.floating_rate_multiplier_schedule[0]
            if floating_rate_calc.floating_rate_multiplier_schedule
            else None
        )
        return StepScheduleResolver(multiplier_schedule)
