import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: qsTr("ESS3 Policy")
	summary: currentState.text
	property string settingsPrefix: "com.victronenergy.settings/Settings/Ess3Policy"
	property string servicePrefix: "fbo.Ess3Policy.Controller"
	property string cgwacsPath: "com.victronenergy.settings/Settings/CGwacs"

	property VBusItem currentState: VBusItem { bind: Utils.path(servicePrefix,"/State") }
	property VBusItem controllerPolicy: VBusItem { bind: Utils.path(settingsPrefix,"/Policy") }
	property VBusItem hub4Mode: VBusItem { bind: Utils.path(cgwacsPath,"/Hub4Mode") }

	property VBusItem ess3policyState: VBusItem { bind: Utils.path(servicePrefix,"/State") }
	property VBusItem ess3policyChargeLeftRegular: VBusItem { bind: Utils.path(servicePrefix,"/ChargeLeftRegular") }
	property VBusItem ess3policyChargeLeftReserve: VBusItem { bind: Utils.path(servicePrefix,"/ChargeLeftReserve") }
	property VBusItem ess3policyChargeMissing: VBusItem { bind: Utils.path(servicePrefix,"/ChargeMissing") }
	property VBusItem ess3policyTimeTillCharged: VBusItem { bind: Utils.path(servicePrefix,"/TimeTillCharged") }
	property VBusItem ess3policyTimeTillDischargedRegular: VBusItem { bind: Utils.path(servicePrefix,"/TimeTillDischargedRegular") }
	property VBusItem ess3policyTimeTillDischargedReserve: VBusItem { bind: Utils.path(servicePrefix,"/TimeTillDischargedReserve") }
	property VBusItem soc: VBusItem { bind: "com.victronenergy.battery/Soc" }

	model: VisualModels {
		VisualItemModel {

			MbItemRow {
				description: qsTr("State")
				values: MbColumn {
					spacing: 2
					MbRow {
						MbTextBlock { item: ess3policyState; width: 90; height: 25 }
					}
				}
			}
			MbItemRow {
				height: 90
				description: qsTr("Energy&Time")
				values: MbColumn {
					spacing: 2
					MbRow {
						MbTextValue { text: "Reserve"; width: 90; height: 20 }
						MbTextValue { text: "Low"; width: 90; height: 20 }
						MbTextValue { text: "High"; width: 90; height: 20 }
					}
					MbRow {
						MbTextBlock { item: ess3policyChargeLeftReserve; width: 90; height: 25 }
						MbTextBlock { item: ess3policyChargeLeftRegular; width: 90; height: 25 }
						MbTextBlock { item: ess3policyChargeMissing; width: 90;height: 25 }
					}
					MbRow {
						MbTextBlock { item: ess3policyTimeTillDischargedReserve; width: 90;height: 25 }
						MbTextBlock { item: ess3policyTimeTillDischargedRegular; width: 90;height: 25 }
						MbTextBlock { item: ess3policyTimeTillCharged; width: 90;height: 25 }
					}
				}
			}
			MbItemOptions {
				description: qsTr("Controller policy")
				bind: Utils.path(settingsPrefix,"/Policy")
				possibleValues: [
					MbOption { description: qsTr("Disable (Prio:Grid)"); value: 0 },
					MbOption { description: qsTr("Solar UPS (Prio:PV,Grid,Bat)"); value: 1 },
					MbOption { description: qsTr("Self consumption (Prio:PV,Bat,Grid)"); value: 2 },
					MbOption { description: qsTr("Bulk recharge (Prio:PV,Grid)"); value: 3 }
				]
			}
			MbItemOptions {
				description: qsTr("Debug level")
				bind: Utils.path(settingsPrefix,"/DebugLevel")
				possibleValues: [
					MbOption { description: qsTr("Only Critical"); value: 50 },
					MbOption { description: qsTr("+Errors"); value: 40 },
					MbOption { description: qsTr("+Warnings"); value: 30 },
					MbOption { description: qsTr("+Information"); value: 20 },
					MbOption { description: qsTr("+Debug messages"); value: 10 }
				]
			}
			MbSubMenu {
				id: idPageSettingsEss3PolicyProtection
				description: qsTr("Battery protection settings")
				subpage: Component { PageSettingsEss3PolicyProtection {} }
			}
			MbSubMenu {
				id: idPageSettingsEss3PolicyBulkRecharge
				description: qsTr("Bulk recharge settings")
				subpage: Component { PageSettingsEss3PolicyBulkRecharge {} }
			}
			MbSubMenu {
				id: idPageSettingsEss3PolicyExcess
				description: qsTr("Excessive power")
				subpage: Component { PageSettingsEss3PolicyExcess {} }
			}

			MbSpinBox {
				id: idSocDischargeLowStart
				description: qsTr("Lower SOC limit when grid is available")
				writeAccessLevel: User.AccessInstaller
				item {
					bind: Utils.path(settingsPrefix,"/SocDischargeLowStart")
					decimals: 0
					unit: "%"
					min: 10
					max: 99
					step: 1
				}
			}
			MbSpinBox {
				id: idBatteryAmpHours
				description: qsTr("Battery full charge in Ampere hours")
				writeAccessLevel: User.AccessInstaller
				item {
					bind: Utils.path(settingsPrefix,"/BatteryAmpereHours")
					decimals: 0
					unit: "Ah"
					min: 1
					max: 10000
					step: 1
				}
			}
		}
	}
}
