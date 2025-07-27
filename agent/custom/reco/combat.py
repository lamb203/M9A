import json
from typing import Union, Optional

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from maa.define import RectType

from utils import logger


@AgentServer.custom_recognition("StagePromotionComplete")
class StagePromotionComplete(CustomRecognition):
    """
    推图模式完成判断（当前关为满星且无下一关）
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> Union[CustomRecognition.AnalyzeResult, Optional[RectType]]:

        cur_flag = False
        # 轶事
        reco_detail = context.run_recognition(
            "StagePromotionCurStageComplete", argv.image
        )
        # 故事模式
        reco_detail1 = context.run_recognition(
            "StagePromotionCurStageComplete1", argv.image
        )
        # 探索模式
        reco_detail2 = context.run_recognition(
            "StagePromotionCurStageComplete2", argv.image
        )
        if reco_detail is not None:
            if reco_detail.best_result:
                cur_flag = True
        if reco_detail1 is not None:
            if reco_detail1.best_result:
                cur_flag = True
        if reco_detail2 is not None:
            if reco_detail2.best_result:
                cur_flag = True

        if cur_flag:
            reco_detail = context.run_recognition(
                "StagePromotionClickNextStage", argv.image
            )
            if reco_detail is not None:
                if not reco_detail.best_result:
                    return [0, 0, 0, 0]
            else:
                return [0, 0, 0, 0]
        return None

@AgentServer.custom_recognition("CombatHandler")
class CombatHandler(CustomRecognition):
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> Union[CustomRecognition.AnalyzeResult, Optional[RectType]]:
        
        try:
            params = json.loads(argv.custom_recognition_param)
            combat_node = params.get("combat_node", "DefaultCombatProcess")
            victory_node = params.get("victory_node","DefaultCombatVictory")
            # 检查战斗进行状态
            combat_result = context.run_recognition(combat_node, argv.image)
            if combat_result and combat_result.best_result:
                # 战斗中，继续等待
                return  CustomRecognition.AnalyzeResult(
                    box=combat_result.best_result.box,
                    detail="战斗进行中，运行战斗处理节点："+ combat_node
                )
        
            # 检查战斗胜利状态
            victory_result = context.run_recognition(victory_node, argv.image)
            if victory_result and victory_result.best_result:
                # 执行胜利动作
                context.run_action(victory_node, victory_result.best_result.box)
                return  CustomRecognition.AnalyzeResult(
                    box=victory_result.best_result.box,
                    detail="战斗胜利，运行胜利处理节点："+ victory_node
                )

            return None
            
        except Exception as e:
            logger.error(f"CombatHandler 执行出错: {e}")
            return None